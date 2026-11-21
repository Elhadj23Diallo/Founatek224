"""Abonnements Basic / Pro payés par carte avec renouvellement automatique (Stripe).

Fonctionnement :
- le client choisit une formule et coche la case d'accord (CGV, renouvellement
  automatique, début immédiat du service) ; le serveur crée une session Stripe
  Checkout en mode « subscription ». Stripe garde la carte, jamais le site ;
- chaque mois, Stripe prélève et envoie « invoice.paid » : le site prolonge
  l'abonnement jusqu'à la fin de la période payée ;
- en cas d'échec (« invoice.payment_failed »), Stripe réessaie et le client
  reçoit un e-mail ; s'il ne paie pas, l'abonnement expire à la fin de la
  période déjà payée (avec quelques jours de grâce, voir utils) ;
- résilier / annuler la résiliation sur le site met à jour Stripe ;
- le portail client Stripe permet de changer de carte.

Le site gardant les abonnements « manuels » (30 jours payés par wallet ou
PayPal), un client qui a encore des jours payés commence le prélèvement à la
fin de ces jours (période d'essai Stripe), sans payer deux fois.
Désactivé tant que STRIPE_AUTO_RENEW_ENABLED n'est pas à true dans le .env.
"""
import logging
from datetime import datetime, time, timedelta
from datetime import timezone as dt_timezone
from decimal import Decimal

import stripe
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.core.mail import send_mail
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from .consumer_law import waiver_from_request
from .models import PaymentRequest, Subscription, Transaction
from .utils import PLAN_PRICES, award_referral_commission, sync_subscription_expiry

logger = logging.getLogger(__name__)

SAAS_KIND = "saas_subscription"
MIN_TRIAL = timedelta(hours=49)  # Stripe Checkout exige une fin d'essai à plus de 48 h

WAIVER_ERROR = (
    "Coche la case : tu acceptes les CGV et le renouvellement automatique chaque mois, "
    "et tu demandes que le service commence tout de suite."
)
SUBMIT_MESSAGE = (
    "Abonnement renouvelé automatiquement chaque mois jusqu'à résiliation, "
    "résiliable à tout moment depuis la page Abonnement du site."
)


class SaasBillingError(Exception):
    def __init__(self, message, status):
        super().__init__(message)
        self.status = status


def auto_renew_enabled():
    return bool(getattr(settings, "STRIPE_ENABLED", False) and getattr(settings, "STRIPE_AUTO_RENEW_ENABLED", False))


def _stripe():
    stripe.api_key = settings.STRIPE_SECRET_KEY
    return stripe


def _plain(obj):
    if obj is None:
        return {}
    return obj.to_dict() if hasattr(obj, "to_dict") else obj


def _id(value):
    if isinstance(value, dict):
        return value.get("id") or ""
    return value or ""


# ----------------------------------------------------------------------------
# Lecture des objets Stripe (anciennes et nouvelles versions de l'API)
# ----------------------------------------------------------------------------

def invoice_subscription_id(invoice):
    sid = _id(invoice.get("subscription"))
    if sid:
        return sid
    details = (invoice.get("parent") or {}).get("subscription_details") or {}
    return _id(details.get("subscription"))


def invoice_metadata(invoice):
    for source in (
        (invoice.get("subscription_details") or {}).get("metadata"),
        ((invoice.get("parent") or {}).get("subscription_details") or {}).get("metadata"),
    ):
        if source:
            return dict(source)
    for line in (invoice.get("lines") or {}).get("data") or []:
        if line.get("metadata"):
            return dict(line["metadata"])
    return {}


def invoice_period_end(invoice):
    ends = [
        (line.get("period") or {}).get("end")
        for line in (invoice.get("lines") or {}).get("data") or []
    ]
    ends = [end for end in ends if end]
    return max(ends) if ends else invoice.get("period_end")


def _payment_intent_from_payments(invoice):
    for item in (invoice.get("payments") or {}).get("data") or []:
        pi = _id((item.get("payment") or {}).get("payment_intent"))
        if pi:
            return pi
    return ""


def invoice_payment_intent(invoice):
    """PaymentIntent de la facture, pour retrouver ce paiement lors d'un remboursement."""
    pi = _id(invoice.get("payment_intent")) or _payment_intent_from_payments(invoice)
    if pi or not invoice.get("id"):
        return pi
    try:
        full = _plain(_stripe().Invoice.retrieve(invoice["id"], expand=["payments"]))
        return _id(full.get("payment_intent")) or _payment_intent_from_payments(full)
    except Exception:
        logger.warning("PaymentIntent introuvable pour la facture %s", invoice.get("id"))
        return ""


def _metadata_from_stripe(subscription_id):
    try:
        return dict(_plain(_stripe().Subscription.retrieve(subscription_id)).get("metadata") or {})
    except Exception:
        logger.warning("Abonnement Stripe %s introuvable", subscription_id)
        return {}


def _local_sub(subscription_id, metadata, lock=True):
    qs = Subscription.objects.select_for_update() if lock else Subscription.objects
    if subscription_id:
        sub = qs.filter(stripe_subscription_id=subscription_id).first()
        if sub:
            return sub
    if (metadata or {}).get("kind") == SAAS_KIND and str(metadata.get("user_id", "")).isdigit():
        Subscription.objects.get_or_create(user_id=int(metadata["user_id"]))
        return qs.get(user_id=int(metadata["user_id"]))
    return None


def _date_from_timestamp(ts):
    return timezone.localtime(datetime.fromtimestamp(int(ts), tz=dt_timezone.utc)).date()


def _send(user, subject, body):
    if not user.email:
        return
    send_mail(
        subject=f"FOUNATEK — {subject}",
        message=f"Bonjour {user.username},\n\n{body}\n\n— FOUNATEK",
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=True,
    )


# ----------------------------------------------------------------------------
# Souscription
# ----------------------------------------------------------------------------

def create_saas_checkout_session(user, plan, success_url, cancel_url, waiver_accepted=False):
    if not auto_renew_enabled():
        raise SaasBillingError("Le paiement par carte avec renouvellement automatique n'est pas encore ouvert.", 503)
    if PLAN_PRICES.get(plan, 0) <= 0:
        raise SaasBillingError("Formule invalide.", 400)

    sub, _ = Subscription.objects.get_or_create(user=user)
    sub = sync_subscription_expiry(sub)
    if sub.billing == "stripe_auto" and sub.stripe_subscription_id:
        if sub.cancel_at_period_end:
            raise SaasBillingError(
                "Ton abonnement par carte est résilié mais encore actif : annule la résiliation "
                "plutôt que de souscrire à nouveau.", 409)
        raise SaasBillingError("Ton abonnement est déjà renouvelé automatiquement par carte.", 409)

    trial_end = None
    today = timezone.localdate()
    if sub.plan != "free" and sub.end_date and sub.end_date >= today:
        if sub.plan != plan:
            raise SaasBillingError(
                f"Ton abonnement {sub.plan.upper()} est déjà payé jusqu'au {sub.end_date:%d/%m/%Y}. "
                f"Choisis la même formule pour activer le prélèvement automatique à partir de cette date, "
                f"ou change de formule quand ta période sera terminée.", 409)
        first_charge = timezone.make_aware(datetime.combine(sub.end_date + timedelta(days=1), time.min))
        if first_charge - timezone.now() >= MIN_TRIAL:
            trial_end = int(first_charge.timestamp())

    if not waiver_accepted:
        raise SaasBillingError(WAIVER_ERROR, 400)

    metadata = {"kind": SAAS_KIND, "plan": plan, "user_id": str(user.pk), "consent": "accepted"}
    subscription_data = {"metadata": metadata}
    if trial_end:
        subscription_data["trial_end"] = trial_end
    params = {
        "mode": "subscription",
        "line_items": [{
            "price_data": {
                "currency": "eur",
                "unit_amount": int(PLAN_PRICES[plan] * 100),
                "recurring": {"interval": "month"},
                "product_data": {"name": f"FOUNATEK — abonnement {plan.capitalize()}"},
            },
            "quantity": 1,
        }],
        "client_reference_id": str(user.pk),
        "metadata": metadata,
        "subscription_data": subscription_data,
        "custom_text": {"submit": {"message": SUBMIT_MESSAGE}},
        "success_url": success_url,
        "cancel_url": cancel_url,
    }
    if sub.stripe_customer_id:
        params["customer"] = sub.stripe_customer_id
    elif user.email:
        params["customer_email"] = user.email

    session = _stripe().checkout.Session.create(**params)
    sub.auto_renew_consent_at = timezone.now()
    sub.save(update_fields=["auto_renew_consent_at"])
    return session


def _plan_from_request(request):
    plan = request.POST.get("plan")
    if plan is None and (request.content_type or "").startswith("application/json"):
        import json
        try:
            plan = (json.loads(request.body or b"{}") or {}).get("plan")
        except ValueError:
            plan = None
    return plan


@login_required
@require_POST
def create_saas_checkout(request):
    back = request.build_absolute_uri(reverse("monetisation:monetisation_abonnement"))
    try:
        session = create_saas_checkout_session(
            request.user, _plan_from_request(request), f"{back}?carte=ok", f"{back}?carte=annule",
            waiver_accepted=waiver_from_request(request),
        )
    except SaasBillingError as exc:
        return JsonResponse({"error": str(exc)}, status=exc.status)
    except stripe.StripeError:
        logger.exception("Création de l'abonnement Stripe impossible")
        return JsonResponse({"error": "Impossible de préparer le paiement, réessaie dans un instant."}, status=502)
    return JsonResponse({"url": session.url})


@login_required
@require_POST
def billing_portal(request):
    """Portail client Stripe : changer de carte, voir les factures."""
    back = request.build_absolute_uri(reverse("monetisation:monetisation_abonnement"))
    sub = Subscription.objects.filter(user=request.user).first()
    if not auto_renew_enabled() or not sub or not sub.stripe_customer_id:
        messages.error(request, "Aucune carte enregistrée pour ton abonnement.")
        return redirect(back)
    try:
        portal = _stripe().billing_portal.Session.create(customer=sub.stripe_customer_id, return_url=back)
    except stripe.StripeError:
        logger.error("Portail client Stripe indisponible (à activer dans le tableau de bord Stripe ?)", exc_info=True)
        messages.error(request, "La gestion de la carte n'est pas disponible pour le moment.")
        return redirect(back)
    return redirect(portal.url)


# ----------------------------------------------------------------------------
# Résiliation depuis le site
# ----------------------------------------------------------------------------

def set_stripe_cancel_at_period_end(sub, value):
    """Programme ou annule la résiliation chez Stripe. Lève stripe.StripeError."""
    _stripe().Subscription.modify(sub.stripe_subscription_id, cancel_at_period_end=bool(value))


def cancel_stripe_subscription_now(subscription_id):
    """Arrête immédiatement les prélèvements (ex. abonnement remboursé)."""
    if not subscription_id or not auto_renew_enabled():
        return
    try:
        _stripe().Subscription.cancel(subscription_id)
    except stripe.StripeError:
        logger.error("Impossible d'arrêter l'abonnement Stripe %s : à faire dans le tableau de bord",
                     subscription_id, exc_info=True)


# ----------------------------------------------------------------------------
# Webhooks (signature déjà vérifiée par stripe_payments.stripe_webhook)
# ----------------------------------------------------------------------------

def handle_checkout_completed(session):
    metadata = session.get("metadata") or {}
    user_id = str(metadata.get("user_id", ""))
    if session.get("mode") != "subscription" or not user_id.isdigit() \
            or str(session.get("client_reference_id")) != user_id:
        logger.warning("Session d'abonnement Stripe invalide : %s", session.get("id"))
        return
    with transaction.atomic():
        Subscription.objects.get_or_create(user_id=int(user_id))
        sub = Subscription.objects.select_for_update().get(user_id=int(user_id))
        sub.billing = "stripe_auto"
        sub.stripe_customer_id = _id(session.get("customer")) or sub.stripe_customer_id
        sub.stripe_subscription_id = _id(session.get("subscription")) or sub.stripe_subscription_id
        sub.cancel_at_period_end = False
        sub.save(update_fields=["billing", "stripe_customer_id", "stripe_subscription_id", "cancel_at_period_end"])


def handle_invoice_paid(invoice):
    subscription_id = invoice_subscription_id(invoice)
    if not subscription_id:
        return  # facture hors abonnement
    metadata = invoice_metadata(invoice)
    if metadata.get("kind") not in (None, SAAS_KIND):
        return
    if not metadata and not Subscription.objects.filter(stripe_subscription_id=subscription_id).exists():
        metadata = _metadata_from_stripe(subscription_id)

    with transaction.atomic():
        sub = _local_sub(subscription_id, metadata)
        if sub is None:
            logger.error("Facture Stripe payée pour un abonnement inconnu : %s", subscription_id)
            return
        if sub.last_stripe_invoice_id == invoice.get("id") or PaymentRequest.objects.filter(
                provider="stripe", transaction_id=invoice.get("id")).exists():
            return  # Stripe redélivre souvent le même événement

        plan = metadata.get("plan") or sub.plan
        sub.billing = "stripe_auto"
        sub.stripe_subscription_id = subscription_id
        sub.stripe_customer_id = _id(invoice.get("customer")) or sub.stripe_customer_id
        sub.last_stripe_invoice_id = invoice.get("id") or ""
        fields = ["billing", "stripe_subscription_id", "stripe_customer_id", "last_stripe_invoice_id"]

        amount_cents = invoice.get("amount_paid") or 0
        if amount_cents == 0:
            sub.save(update_fields=fields)  # début de période d'essai : jours déjà payés
            return
        expected = int(PLAN_PRICES.get(plan, 0) * 100)
        if invoice.get("currency") != "eur" or amount_cents != expected:
            sub.save(update_fields=fields)
            logger.error("Facture Stripe %s inattendue : %s %s pour le plan %s",
                         invoice.get("id"), amount_cents, invoice.get("currency"), plan)
            return

        first_payment = sub.plan != plan or sub.end_date is None
        sub.plan = plan
        sub.end_date = _date_from_timestamp(invoice_period_end(invoice))
        sub.save(update_fields=fields + ["plan", "end_date"])

        amount = Decimal(amount_cents) / 100
        payment = PaymentRequest.objects.create(
            user=sub.user, provider="stripe", phone_number="", amount=amount, amount_local=amount,
            currency_local="EUR", status="success", transaction_id=invoice.get("id"),
            external_id=invoice_payment_intent(invoice), purpose="subscription",
        )
        Transaction.objects.create(
            user=sub.user, type="subscription", amount=amount,
            description=f"Abonnement {plan} — prélèvement automatique par carte",
        )
        award_referral_commission(
            sub.user, amount, f"Commission sur l'abonnement de {sub.user.username}", payment=payment,
        )
        user, end_date = sub.user, sub.end_date
        transaction.on_commit(lambda: _send(
            user,
            f"Abonnement {plan.upper()} {'activé' if first_payment else 'renouvelé'}",
            f"Ton paiement de {amount} € par carte a bien été reçu. Ton abonnement {plan.upper()} "
            f"est actif jusqu'au {end_date:%d/%m/%Y} et sera renouvelé automatiquement chaque mois. "
            f"Tu peux le résilier à tout moment depuis la page Abonnement du site.",
        ))


def handle_invoice_payment_failed(invoice):
    subscription_id = invoice_subscription_id(invoice)
    if not subscription_id:
        return
    sub = _local_sub(subscription_id, invoice_metadata(invoice), lock=False)
    if sub is None:
        return
    key = f"saas-failed-{invoice.get('id')}-{invoice.get('attempt_count')}"
    if not cache.add(key, 1, timeout=7 * 24 * 3600):
        return  # e-mail déjà envoyé pour cette tentative
    _send(
        sub.user,
        "Le prélèvement de ton abonnement a échoué",
        f"Le paiement par carte de ton abonnement {sub.plan.upper()} n'a pas pu être effectué. "
        f"Stripe va réessayer automatiquement dans les prochains jours.\n\n"
        f"Pour éviter une interruption, vérifie ta carte ou remplace-la depuis la page Abonnement "
        f"du site ({settings.SITE_URL}/monetisation/abonnement/), bouton « Gérer ma carte ».",
    )


def handle_subscription_updated(obj):
    status = obj.get("status")
    if status in ("canceled", "incomplete_expired"):
        handle_subscription_deleted(obj)
        return
    with transaction.atomic():
        sub = _local_sub(obj.get("id"), obj.get("metadata") or {})
        if sub is None or sub.billing != "stripe_auto":
            return
        cancelling = bool(obj.get("cancel_at_period_end") or obj.get("cancel_at"))
        if sub.cancel_at_period_end != cancelling:
            sub.cancel_at_period_end = cancelling
            sub.save(update_fields=["cancel_at_period_end"])


def handle_subscription_deleted(obj):
    with transaction.atomic():
        sub = _local_sub(obj.get("id"), obj.get("metadata") or {})
        if sub is None or sub.stripe_subscription_id != obj.get("id"):
            return
        sub.billing = "manual"
        sub.stripe_subscription_id = ""
        # Les jours déjà payés restent acquis ; ensuite, retour au gratuit.
        sub.cancel_at_period_end = bool(sub.plan != "free" and sub.end_date)
        sub.save(update_fields=["billing", "stripe_subscription_id", "cancel_at_period_end"])
        sync_subscription_expiry(sub)


EVENT_HANDLERS = {
    "invoice.paid": handle_invoice_paid,
    "invoice.payment_failed": handle_invoice_payment_failed,
    "customer.subscription.updated": handle_subscription_updated,
    "customer.subscription.deleted": handle_subscription_deleted,
}
