"""Remboursements et litiges (Stripe et PayPal) pour le wallet.

Règles appliquées automatiquement :
- recharge remboursée : le montant remboursé est retiré du wallet (le solde
  peut devenir négatif si le client l'avait déjà dépensé) ;
- abonnement payé directement par PayPal puis remboursé : retour au plan
  gratuit ;
- litige ouvert (contestation auprès de la banque / de PayPal) : le montant
  contesté est bloqué, c'est-à-dire retiré du wallet ;
  litige gagné : il est rendu ; litige perdu : il reste retiré ;
- la commission de parrainage NON convertie liée au paiement est annulée ;
- l'admin reçoit un e-mail à chaque fois.

Chaque fonction est idempotente : un même événement reçu deux fois ne
débite jamais deux fois (Stripe et PayPal redélivrent souvent).

Les commandes de la boutique (shop) remboursées ou contestées sont gérées
dans founatekapp.stripe_checkout.
"""
import json
import logging
from decimal import Decimal

import requests
import stripe
from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from .models import PaymentRequest, ReferralTransaction, Subscription, Transaction, Wallet
from .utils import round_money

logger = logging.getLogger(__name__)
ZERO = Decimal("0")


def send_admin_alert(subject, body):
    from .signals import ADMIN_NOTIFICATION_EMAILS
    try:
        send_mail(
            subject=f"[FOUNATEK] {subject}",
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=ADMIN_NOTIFICATION_EMAILS,
            fail_silently=True,
        )
    except Exception:
        logger.exception("Envoi de l'alerte admin impossible")


def _cancel_commissions(payment):
    """Annule les commissions non converties du paiement. Retourne
    (annulées, déjà converties)."""
    pending = ReferralTransaction.objects.filter(payment=payment, converted=False)
    cancelled = pending.count()
    pending.delete()
    converted = ReferralTransaction.objects.filter(payment=payment, converted=True).count()
    return cancelled, converted


def _commission_note(cancelled, converted):
    note = ""
    if cancelled:
        note += f"\n{cancelled} commission(s) de parrainage annulée(s)."
    if converted:
        note += f"\n{converted} commission(s) déjà convertie(s) en crédits : à vérifier à la main."
    return note


def _wallet(user):
    wallet, _ = Wallet.objects.select_for_update().get_or_create(user=user, defaults={"balance": 0})
    return wallet


def _downgrade_to_free(user):
    sub, _ = Subscription.objects.select_for_update().get_or_create(user=user)
    stripe_subscription_id = sub.stripe_subscription_id if sub.billing == "stripe_auto" else ""
    sub.plan = "free"
    sub.end_date = None
    sub.cancel_at_period_end = False
    if stripe_subscription_id:
        # Abonnement remboursé : on arrête aussi les prélèvements automatiques.
        from .saas_billing import cancel_stripe_subscription_now
        sub.billing = "manual"
        sub.stripe_subscription_id = ""
        transaction.on_commit(lambda: cancel_stripe_subscription_now(stripe_subscription_id))
    sub.save()


def apply_refund(payment_id, refunded_total, source, reference=""):
    """`refunded_total` : total remboursé À CE JOUR pour ce paiement (cumulé).
    Retourne le montant nouvellement traité (0 si rien de neuf)."""
    with transaction.atomic():
        payment = PaymentRequest.objects.select_for_update().get(pk=payment_id)
        if reference and Transaction.objects.filter(user=payment.user, description__contains=reference).exists():
            return ZERO  # ce remboursement précis a déjà été traité
        refunded_total = min(round_money(refunded_total), payment.amount)
        delta = round_money(refunded_total - payment.refunded_amount)
        if delta <= 0:
            return ZERO

        ref_txt = f" [{reference}]" if reference else ""
        if payment.purpose == "subscription":
            _downgrade_to_free(payment.user)
            Transaction.objects.create(
                user=payment.user, type="debit", amount=delta,
                description=f"Remboursement {source} : abonnement annulé{ref_txt}",
            )
            detail = "L'abonnement est repassé au plan gratuit."
        else:
            wallet = _wallet(payment.user)
            wallet.balance = round_money(wallet.balance - delta)
            wallet.save()
            Transaction.objects.create(
                user=payment.user, type="debit", amount=delta,
                description=f"Remboursement {source} de la recharge{ref_txt}",
            )
            detail = f"{delta} € retirés du wallet (nouveau solde : {wallet.balance} €)."

        payment.refunded_amount = refunded_total
        if refunded_total >= payment.amount:
            payment.status = "refunded"
        payment.save(update_fields=["refunded_amount", "status"])
        cancelled, converted = _cancel_commissions(payment)
        body = (f"Paiement {source} de {payment.user.username} remboursé : {delta} € "
                f"(total remboursé {refunded_total} € sur {payment.amount} €).\n{detail}"
                + _commission_note(cancelled, converted))
        transaction.on_commit(lambda: send_admin_alert(f"Remboursement {source} — {payment.user.username}", body))
        return delta


def apply_dispute_opened(payment_id, amount, source):
    """Litige ouvert : le montant contesté est bloqué (retiré du wallet)."""
    with transaction.atomic():
        payment = PaymentRequest.objects.select_for_update().get(pk=payment_id)
        if payment.status != "success" or payment.disputed_amount > 0:
            return False
        amount = min(round_money(amount), round_money(payment.amount - payment.refunded_amount))
        if amount <= 0:
            return False
        if payment.purpose == "subscription":
            detail = "Abonnement payé directement : rien à retirer du wallet."
        else:
            wallet = _wallet(payment.user)
            wallet.balance = round_money(wallet.balance - amount)
            wallet.save()
            Transaction.objects.create(
                user=payment.user, type="debit", amount=amount,
                description=f"Litige {source} en cours : montant bloqué",
            )
            detail = f"{amount} € bloqués (retirés du wallet, nouveau solde : {wallet.balance} €)."
        payment.status = "disputed"
        payment.disputed_amount = amount
        payment.save(update_fields=["status", "disputed_amount"])
        body = (f"{payment.user.username} conteste un paiement {source} de {amount} €.\n{detail}\n"
                f"Réponds au litige depuis ton tableau de bord {source} avant la date limite.")
        transaction.on_commit(lambda: send_admin_alert(f"Litige {source} ouvert — {payment.user.username}", body))
        return True


def apply_dispute_closed(payment_id, won, source):
    """Litige terminé : gagné -> montant rendu ; perdu -> il reste retiré."""
    with transaction.atomic():
        payment = PaymentRequest.objects.select_for_update().get(pk=payment_id)
        if payment.status != "disputed":
            return False
        amount = payment.disputed_amount
        if won:
            if payment.purpose != "subscription":
                wallet = _wallet(payment.user)
                wallet.balance = round_money(wallet.balance + amount)
                wallet.save()
                Transaction.objects.create(
                    user=payment.user, type="credit", amount=amount,
                    description=f"Litige {source} gagné : montant débloqué",
                )
            payment.status = "success"
            note = "Litige gagné : le montant a été rendu au wallet." if payment.purpose != "subscription" else "Litige gagné."
        else:
            if payment.purpose == "subscription":
                _downgrade_to_free(payment.user)
            payment.refunded_amount = round_money(payment.refunded_amount + amount)
            payment.status = "refunded"
            cancelled, converted = _cancel_commissions(payment)
            note = ("Litige perdu : le montant reste retiré."
                    + (" L'abonnement est repassé au plan gratuit." if payment.purpose == "subscription" else "")
                    + _commission_note(cancelled, converted))
        payment.disputed_amount = ZERO
        payment.save(update_fields=["status", "disputed_amount", "refunded_amount"])
        body = f"Litige {source} de {payment.user.username} ({amount} €) terminé.\n{note}"
        transaction.on_commit(lambda: send_admin_alert(f"Litige {source} terminé — {payment.user.username}", body))
        return True


# ============================ Stripe ============================

def _stripe_payment_for(payment_intent_id):
    """Retrouve ce que paie un PaymentIntent : ("wallet", PaymentRequest),
    ("shop", Order), ("academy" | "parcours", paiement de contenu) ou (None, None)."""
    from founatekapp.models import Order
    from .content_refunds import find_content_payment

    if not payment_intent_id:
        return None, None
    payment = PaymentRequest.objects.filter(provider="stripe", external_id=payment_intent_id).first()
    if payment:
        return "wallet", payment
    order = Order.objects.filter(card_payment_id=payment_intent_id).first()
    if order:
        return "shop", order
    kind, content = find_content_payment("stripe", reference=payment_intent_id)
    if content:
        return kind, content
    # Paiements confirmés avant l'enregistrement du PaymentIntent : on
    # demande à Stripe quelle session Checkout correspond.
    try:
        stripe.api_key = settings.STRIPE_SECRET_KEY
        sessions = stripe.checkout.Session.list(payment_intent=payment_intent_id, limit=1)
        session_id = sessions.data[0].id if sessions.data else None
    except (stripe.StripeError, AttributeError, IndexError):
        logger.exception("Session Stripe introuvable pour %s", payment_intent_id)
        session_id = None
    if session_id:
        payment = PaymentRequest.objects.filter(provider="stripe", transaction_id=session_id).first()
        if payment:
            PaymentRequest.objects.filter(pk=payment.pk).update(external_id=payment_intent_id)
            return "wallet", payment
        order = Order.objects.filter(stripe_session_id=session_id).first()
        if order:
            Order.objects.filter(pk=order.pk).update(card_payment_id=payment_intent_id)
            return "shop", order
        kind, content = find_content_payment("stripe", checkout_id=session_id)
        if content:
            return kind, content
    return None, None


def _unknown_payment_alert(what, reference, amount_label):
    logger.warning("%s Stripe pour un paiement inconnu (%s)", what, reference)
    send_admin_alert(
        f"{what} Stripe à vérifier",
        f"{what} reçu de Stripe ({amount_label}, {reference}) mais le paiement correspondant est "
        f"introuvable sur le site. Vérifie dans le tableau de bord Stripe.",
    )


def handle_stripe_charge_refunded(charge):
    pi = charge.get("payment_intent")
    refunded_cents = charge.get("amount_refunded") or 0
    total_cents = charge.get("amount") or 0
    kind, target = _stripe_payment_for(pi)
    if kind == "wallet":
        apply_refund(target.pk, Decimal(refunded_cents) / 100, "Stripe")
    elif kind == "shop":
        from founatekapp.stripe_checkout import handle_shop_order_refunded
        handle_shop_order_refunded(target.pk, refunded_cents, total_cents)
    elif kind in ("academy", "parcours"):
        from .content_refunds import partial_refund_alert, revoke_content_access
        if total_cents and refunded_cents >= total_cents:
            revoke_content_access(kind, target.pk, "refunded", "Stripe", detail=f"PaymentIntent {pi}")
        else:
            partial_refund_alert(kind, target, f"{refunded_cents / 100:.2f} €", "Stripe")
    else:
        _unknown_payment_alert("Remboursement", pi, f"{refunded_cents / 100:.2f} {str(charge.get('currency', '')).upper()}")


def handle_stripe_dispute(dispute, closed):
    pi = dispute.get("payment_intent")
    kind, target = _stripe_payment_for(pi)
    status = dispute.get("status")
    won = status in ("won", "warning_closed")
    if kind == "wallet":
        if closed:
            apply_dispute_closed(target.pk, won, "Stripe")
        else:
            apply_dispute_opened(target.pk, Decimal(dispute.get("amount") or 0) / 100, "Stripe")
    elif kind == "shop":
        from founatekapp.stripe_checkout import handle_shop_order_dispute
        handle_shop_order_dispute(target.pk, closed=closed, won=won)
    elif kind in ("academy", "parcours"):
        from .content_refunds import close_content_dispute, revoke_content_access
        if closed:
            close_content_dispute(kind, target.pk, won, "Stripe")
        else:
            revoke_content_access(kind, target.pk, "disputed", "Stripe", detail=f"PaymentIntent {pi}")
    else:
        _unknown_payment_alert("Litige", pi, f"{(dispute.get('amount') or 0) / 100:.2f} {str(dispute.get('currency', '')).upper()}")


# ============================ PayPal ============================

def _verify_paypal_webhook(request):
    """Vérifie la signature auprès de PayPal (API verify-webhook-signature).
    L'événement est renvoyé tel quel (corps brut) : le reformater peut faire
    échouer la vérification."""
    fields = {
        "auth_algo": request.headers.get("PAYPAL-AUTH-ALGO", ""),
        "cert_url": request.headers.get("PAYPAL-CERT-URL", ""),
        "transmission_id": request.headers.get("PAYPAL-TRANSMISSION-ID", ""),
        "transmission_sig": request.headers.get("PAYPAL-TRANSMISSION-SIG", ""),
        "transmission_time": request.headers.get("PAYPAL-TRANSMISSION-TIME", ""),
        "webhook_id": settings.PAYPAL_WEBHOOK_ID,
    }
    if not all(fields.values()):
        return False
    body = json.dumps(fields)[:-1] + ', "webhook_event": ' + request.body.decode("utf-8") + "}"
    try:
        resp = requests.post(
            f"{settings.PAYPAL_API_BASE}/v1/notifications/verify-webhook-signature",
            data=body.encode("utf-8"),
            headers={"Content-Type": "application/json"},
            auth=(settings.PAYPAL_CLIENT_ID, settings.PAYPAL_SECRET),
            timeout=20,
        )
        return resp.status_code == 200 and resp.json().get("verification_status") == "SUCCESS"
    except (requests.RequestException, ValueError):
        logger.exception("Vérification du webhook PayPal impossible")
        return False


def _capture_id_from_links(resource):
    for link in resource.get("links") or []:
        if link.get("rel") == "up" and "/captures/" in (link.get("href") or ""):
            return link["href"].rstrip("/").split("/")[-1]
    return None


def _paypal_payment(capture_id):
    if not capture_id:
        return None
    return PaymentRequest.objects.filter(provider="paypal", external_id=capture_id).first()


PAYPAL_SELLER_WINS = {"RESOLVED_SELLER_FAVOUR", "CANCELED_BY_BUYER", "DENIED"}


def handle_paypal_event(event):
    event_type = event.get("event_type", "")
    resource = event.get("resource") or {}

    if event_type == "PAYMENT.CAPTURE.REFUNDED":
        capture_id = _capture_id_from_links(resource)
        payment = _paypal_payment(capture_id)
        if payment is None:
            if not _paypal_content_event(event_type, resource, capture_id):
                _unknown_paypal(event_type, capture_id or resource.get("id"))
            return
        breakdown = (resource.get("seller_payable_breakdown") or {}).get("total_refunded_amount") or {}
        if breakdown.get("value"):
            total = round_money(breakdown["value"])
            reference = ""
        else:
            # Sans total cumulé : on ajoute ce remboursement, une seule fois
            # grâce à sa référence.
            total = round_money(payment.refunded_amount + round_money((resource.get("amount") or {}).get("value", 0)))
            reference = f"PayPal {resource.get('id', '')}"
        apply_refund(payment.pk, total, "PayPal", reference=reference)

    elif event_type == "PAYMENT.CAPTURE.REVERSED":
        # Paiement annulé par PayPal (ex. rétrofacturation) : remboursement total.
        payment = _paypal_payment(resource.get("id"))
        if payment is None:
            if not _paypal_content_event(event_type, resource, resource.get("id")):
                _unknown_paypal(event_type, resource.get("id"))
            return
        apply_refund(payment.pk, payment.amount, "PayPal")

    elif event_type in ("CUSTOMER.DISPUTE.CREATED", "CUSTOMER.DISPUTE.RESOLVED"):
        transactions = resource.get("disputed_transactions") or []
        capture_id = transactions[0].get("seller_transaction_id") if transactions else None
        payment = _paypal_payment(capture_id)
        if payment is None:
            if not _paypal_content_event(event_type, resource, capture_id):
                _unknown_paypal(event_type, capture_id or resource.get("dispute_id"))
            return
        if event_type == "CUSTOMER.DISPUTE.CREATED":
            amount = (resource.get("dispute_amount") or {}).get("value") or payment.amount
            apply_dispute_opened(payment.pk, amount, "PayPal")
        else:
            outcome = (resource.get("dispute_outcome") or {}).get("outcome_code", "")
            apply_dispute_closed(payment.pk, outcome in PAYPAL_SELLER_WINS, "PayPal")


def _paypal_content_event(event_type, resource, capture_id):
    """Pack Livre 1 ou parcours payé par PayPal. Retourne True si traité."""
    from .content_refunds import (
        close_content_dispute, find_content_payment, partial_refund_alert, revoke_content_access,
    )
    kind, content = find_content_payment("paypal", reference=capture_id)
    if content is None:
        return False
    if event_type == "PAYMENT.CAPTURE.REFUNDED":
        breakdown = (resource.get("seller_payable_breakdown") or {}).get("total_refunded_amount") or {}
        refunded = round_money(breakdown.get("value") or (resource.get("amount") or {}).get("value") or 0)
        if refunded >= content.amount_eur:
            revoke_content_access(kind, content.pk, "refunded", "PayPal", detail=f"Capture {capture_id}")
        else:
            partial_refund_alert(kind, content, f"{refunded} €", "PayPal")
    elif event_type == "PAYMENT.CAPTURE.REVERSED":
        revoke_content_access(kind, content.pk, "refunded", "PayPal", detail=f"Capture {capture_id}")
    elif event_type == "CUSTOMER.DISPUTE.CREATED":
        revoke_content_access(kind, content.pk, "disputed", "PayPal", detail=f"Capture {capture_id}")
    elif event_type == "CUSTOMER.DISPUTE.RESOLVED":
        outcome = (resource.get("dispute_outcome") or {}).get("outcome_code", "")
        close_content_dispute(kind, content.pk, outcome in PAYPAL_SELLER_WINS, "PayPal")
    return True


def _unknown_paypal(event_type, reference):
    logger.warning("Webhook PayPal %s pour un paiement inconnu (%s)", event_type, reference)
    send_admin_alert(
        "Événement PayPal à vérifier",
        f"PayPal a envoyé {event_type} ({reference}) pour un paiement introuvable sur le site. "
        f"Vérifie dans ton compte PayPal.",
    )


@csrf_exempt
def paypal_webhook(request):
    """Webhook PayPal (remboursements, rétrofacturations, litiges). Signature
    vérifiée auprès de PayPal avec PAYPAL_WEBHOOK_ID."""
    if request.method != "POST":
        return JsonResponse({"error": "Méthode non autorisée"}, status=405)
    if not settings.PAYPAL_WEBHOOK_ID:
        return JsonResponse({"error": "Webhook PayPal non configuré"}, status=503)
    try:
        event = json.loads(request.body)
    except ValueError:
        return JsonResponse({"error": "JSON invalide"}, status=400)
    if not _verify_paypal_webhook(request):
        return JsonResponse({"error": "Signature invalide"}, status=400)
    handle_paypal_event(event)
    return JsonResponse({"received": True})
