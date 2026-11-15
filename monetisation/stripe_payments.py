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
from .utils import round_money

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

    try:
        session = create_wallet_topup_checkout(request.user, amount, success_url, cancel_url)
    except stripe.StripeError:
        logger.exception("Erreur Stripe lors de la création du Checkout Session")
        return JsonResponse({"error": "Impossible de créer la session de paiement."}, status=502)

    return JsonResponse({"url": session.url})


@login_required
def stripe_success(request):
    """Retour de Stripe Checkout après paiement. N'écrit RIEN en base : seul
    le webhook crédite le wallet (il peut arriver avant ou après cette page)."""
    return render(request, "monetisation/stripe_success.html")


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

    if event["type"] != "checkout.session.completed":
        return JsonResponse({"received": True}, status=200)

    # Depuis stripe-python 13+, les objets Stripe ne sont plus des dict :
    # session.get(...) lève AttributeError (→ erreur 500 renvoyée à Stripe).
    # to_dict() les convertit en vrai dict Python.
    session = event["data"]["object"].to_dict()
    if session.get("payment_status") != "paid":
        return JsonResponse({"received": True}, status=200)

    session_id = session.get("id")

    with transaction.atomic():
        try:
            payment = PaymentRequest.objects.select_for_update().get(
                transaction_id=session_id, provider="stripe"
            )
        except PaymentRequest.DoesNotExist:
            logger.warning("Webhook Stripe pour une session Checkout inconnue: %s", session_id)
            return JsonResponse({"received": True}, status=200)

        if payment.status == "success":
            # Stripe renvoie parfois le même événement plusieurs fois : on ne
            # crédite jamais deux fois la même session.
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
        if hasattr(payment.user, "referred_by"):
            ref = payment.user.referred_by
            commission_points = payment.amount * 0.05 * 1000
            ReferralTransaction.objects.create(
                referral=ref,
                amount=commission_points,
                description=f"Commission sur recharge de {payment.user.username}",
                converted=False,
            )

        payment.status = "success"
        payment.save()

    return JsonResponse({"received": True}, status=200)
