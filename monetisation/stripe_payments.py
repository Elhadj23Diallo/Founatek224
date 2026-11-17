"""Recharge du wallet par carte via Stripe Checkout.

Principe : Stripe ne sert qu'à RECHARGER LE WALLET (par carte). L'abonnement
s'achète ensuite depuis le solde du wallet, comme aujourd'hui — pas d'abonnement
Stripe récurrent, pour éviter de payer les frais Stripe (~1,5 % + 0,25 € en
carte européenne, ~3,15 % + 0,25 € hors Europe) une 2e fois à chaque mois.

Montants : minimum 10 €, maximum 500 €. En dessous de 10 €, les frais Stripe
pèsent trop lourd (≈10-12 % sur une recharge de 3 €, contre ≈4-6 % sur 10 €).

Seul le webhook (`stripe_webhook`) crédite le wallet. La page de retour
(`stripe_success`) n'écrit jamais rien en base : Stripe peut rediriger
l'utilisateur avant même que le webhook soit arrivé.
"""
import json
import logging

import stripe
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt

from .models import PaymentRequest, Wallet, Transaction, ReferralTransaction
from .utils import round_money, award_referral_commission

logger = logging.getLogger(__name__)

STRIPE_TOPUP_CHOICES_EUR = [10, 20, 30, 50]
STRIPE_TOPUP_MIN_EUR = 10
STRIPE_TOPUP_MAX_EUR = 500


def _validate_topup_amount(raw_amount):
    """Retourne le montant (float, 2 décimales) ou lève ValueError(message)."""
    try:
        amount = round_money(raw_amount)
    except (TypeError, ValueError):
        raise ValueError("Montant invalide.")
    if not (STRIPE_TOPUP_MIN_EUR <= amount <= STRIPE_TOPUP_MAX_EUR):
        raise ValueError(
            f"Le montant doit être entre {STRIPE_TOPUP_MIN_EUR} et {STRIPE_TOPUP_MAX_EUR} EUR."
        )
    return amount


def create_wallet_topup_checkout(user, amount, success_url, cancel_url):
    """Cœur partagé web+mobile : crée la session Stripe Checkout et le
    PaymentRequest 'pending' associé. Retourne la Session Stripe créée.
    Lève stripe.StripeError si l'appel à Stripe échoue."""
    stripe.api_key = settings.STRIPE_SECRET_KEY
    session = stripe.checkout.Session.create(
        mode="payment",
        # Les moyens de paiement (carte, etc.) se gèrent désormais dans le
        # tableau de bord Stripe : Paramètres > Moyens de paiement.
        line_items=[{
            "price_data": {
                "currency": "eur",
                "unit_amount": int(round(amount * 100)),
                "product_data": {"name": "Recharge portefeuille FOUNATEK"},
            },
            "quantity": 1,
        }],
        client_reference_id=str(user.id),
        metadata={
            "user_id": str(user.id),
            "amount_eur": f"{amount:.2f}",
            "kind": "wallet_topup",
        },
        success_url=success_url,
        cancel_url=cancel_url,
    )

    PaymentRequest.objects.create(
        user=user,
        provider="stripe",
        amount=amount,
        status="pending",
        transaction_id=session.id,
    )

    return session


@login_required
def stripe_create_checkout(request):
    """POST {"amount": 10} -> {"url": "https://checkout.stripe.com/..."}

    Le front (web ou mobile) ouvre/redirige simplement vers cette url — voir
    aussi mobile_monetisation_stripe_create_checkout (espcontrol/api_views.py)
    pour l'équivalent authentifié par Token, utilisé par l'appli Expo."""
    if request.method != "POST":
        return JsonResponse({"error": "Méthode non autorisée"}, status=405)

    if not settings.STRIPE_ENABLED:
        return JsonResponse({"error": "Paiement par carte indisponible pour le moment."}, status=503)

    try:
        data = json.loads(request.body) if request.body else {}
    except ValueError:
        data = request.POST

    try:
        amount = _validate_topup_amount(data.get("amount"))
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    success_url = request.build_absolute_uri("/monetisation/stripe/success/") + "?session_id={CHECKOUT_SESSION_ID}"
    cancel_url = request.build_absolute_uri("/monetisation/wallet/")
    if data.get("return_to") == "abonnement":
        # Recharge lancée depuis la page Abonnement : on y revient ensuite.
        success_url += "&retour=abonnement"
        cancel_url = request.build_absolute_uri("/monetisation/abonnement/")

    try:
        session = create_wallet_topup_checkout(request.user, amount, success_url, cancel_url)
    except stripe.StripeError:
        logger.exception("Erreur Stripe lors de la création du Checkout Session")
        return JsonResponse({"error": "Impossible de créer la session de paiement."}, status=502)

    return JsonResponse({"url": session.url})


@login_required
def stripe_success(request):
    """Retour de Stripe Checkout après paiement. N'écrit RIEN en base : seul
    le webhook crédite le wallet (il peut arriver avant ou après cette page).
    La page se recharge toute seule jusqu'à ce que le crédit soit visible."""
    session_id = request.GET.get("session_id", "")
    payment = None
    if session_id:
        payment = PaymentRequest.objects.filter(
            transaction_id=session_id, provider="stripe", user=request.user
        ).first()
    next_url = "/monetisation/abonnement/" if request.GET.get("retour") == "abonnement" else None
    return render(request, "monetisation/stripe_success.html", {
        "payment": payment,
        "credited": bool(payment and payment.status == "success"),
        "next_url": next_url,
    })


@csrf_exempt
def stripe_webhook(request):
    """Webhook Stripe — hors de /api/ (donc pas bloqué par APIKeyMiddleware qui
    exige un Token sur ce préfixe) ; authentifié uniquement par la signature
    Stripe-Signature, vérifiée avec STRIPE_WEBHOOK_SECRET."""
    if not settings.STRIPE_ENABLED:
        return JsonResponse({"error": "Stripe non configuré"}, status=503)

    payload = request.body
    sig_header = request.META.get("HTTP_STRIPE_SIGNATURE", "")

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, settings.STRIPE_WEBHOOK_SECRET)
    except (ValueError, stripe.SignatureVerificationError):
        return JsonResponse({"error": "Signature invalide"}, status=400)

    event_type = event["type"]

    # Remboursements et litiges (wallet ou boutique) : voir monetisation/refunds.py
    if event_type in ("charge.refunded", "charge.dispute.created", "charge.dispute.closed"):
        from .refunds import handle_stripe_charge_refunded, handle_stripe_dispute
        obj = event["data"]["object"].to_dict()
        if event_type == "charge.refunded":
            handle_stripe_charge_refunded(obj)
        else:
            handle_stripe_dispute(obj, closed=(event_type == "charge.dispute.closed"))
        return JsonResponse({"received": True}, status=200)

    if event_type not in ("checkout.session.completed", "checkout.session.expired"):
        return JsonResponse({"received": True}, status=200)

    # Depuis stripe-python 13+, les objets Stripe ne sont plus des dict :
    # session.get(...) lève AttributeError (→ erreur 500 renvoyée à Stripe).
    # to_dict() les convertit en vrai dict Python.
    session = event["data"]["object"].to_dict()
    session_id = session.get("id")

    # Un seul webhook Stripe pour tout le projet : on route selon
    # metadata.kind plutôt que de dupliquer un endpoint/secret par app.
    kind = (session.get("metadata") or {}).get("kind")

    if event_type == "checkout.session.expired":
        # Session jamais payée (abandon) : on clôt ce qui l'attendait.
        if kind == "shop_order":
            from founatekapp.stripe_checkout import handle_shop_order_expired
            handle_shop_order_expired(session)
        else:
            PaymentRequest.objects.filter(
                transaction_id=session_id, provider="stripe", status="pending"
            ).update(status="failed")
        return JsonResponse({"received": True}, status=200)

    if session.get("payment_status") != "paid":
        return JsonResponse({"received": True}, status=200)

    if kind == "shop_order":
        from founatekapp.stripe_checkout import handle_shop_order_paid
        handle_shop_order_paid(session)
        return JsonResponse({"received": True}, status=200)

    with transaction.atomic():
        try:
            payment = PaymentRequest.objects.select_for_update().get(
                transaction_id=session_id, provider="stripe"
            )
        except PaymentRequest.DoesNotExist:
            logger.warning("Webhook Stripe pour une session Checkout inconnue: %s", session_id)
            return JsonResponse({"received": True}, status=200)

        if payment.status != "pending":
            # Stripe renvoie parfois le même événement plusieurs fois : on ne
            # crédite jamais deux fois la même session (ni une session déjà
            # remboursée ou contestée).
            return JsonResponse({"received": True, "already_processed": True}, status=200)

        amount_total = session.get("amount_total")
        currency = session.get("currency")
        expected_cents = int(round(payment.amount * 100))

        if currency != "eur" or amount_total != expected_cents:
            logger.warning(
                "Webhook Stripe: montant/devise inattendus pour %s (attendu %.2f EUR, reçu %s %s)",
                session_id, payment.amount, amount_total, currency,
            )
            payment.status = "failed"
            payment.save()
            return JsonResponse({"received": True}, status=200)

        wallet, _ = Wallet.objects.select_for_update().get_or_create(
            user=payment.user, defaults={"balance": 0}
        )
        wallet.balance = round_money(wallet.balance + payment.amount)
        wallet.save()

        Transaction.objects.create(
            user=payment.user,
            type="credit",
            amount=payment.amount,
            description="Recharge par carte (Stripe)",
        )

        # ⚡ Commission au parrain — ici seulement, une fois le paiement
        # confirmé par Stripe (jamais à la création de la session).
        award_referral_commission(
            payment.user, payment.amount,
            f"Commission sur recharge de {payment.user.username}",
            payment=payment,
        )

        payment.status = "success"
        payment.purpose = "credit"
        # PaymentIntent : sert à retrouver ce paiement en cas de remboursement/litige
        payment.external_id = session.get("payment_intent") or ""
        payment.save()

    return JsonResponse({"received": True}, status=200)
