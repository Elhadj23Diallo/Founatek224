"""Achat d'un parcours payant (cours formateur) par Stripe ou PayPal —
indépendant du pack Academy Livre 1 (voir academy_checkout.py) et de la
recharge wallet. Le prix est toujours celui du Parcours en base (jamais
fourni par le client)."""
import logging
from decimal import Decimal

import requests
import stripe
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from iot.models import Parcours, ParcoursAccess, ParcoursPayment
from iot.parcours_access import can_read_parcours
from django.utils import timezone
from .consumer_law import STRIPE_SUBMIT_MESSAGE, WAIVER_ERROR, waiver_from_request

logger = logging.getLogger(__name__)


class ParcoursCheckoutError(Exception):
    """Message à renvoyer tel quel au client, avec le status HTTP associé."""

    def __init__(self, message, status):
        super().__init__(message)
        self.status = status


def create_parcours_checkout_session(user, parcours, success_url, cancel_url, waiver_accepted=False):
    """Cœur partagé web + mobile : mêmes vérifications, même session Stripe.
    Lève ParcoursCheckoutError (message + status à renvoyer tel quel) ou
    stripe.StripeError. Retourne la Session Stripe créée."""
    if not parcours.is_published:
        raise ParcoursCheckoutError("Ce parcours n'est pas disponible.", 404)
    if not parcours.prix or parcours.prix <= 0:
        raise ParcoursCheckoutError("Ce parcours est gratuit.", 400)
    # « Déjà acquis » passe avant « paiement indisponible » : un acheteur
    # n'a pas à apprendre que Stripe est coupé pour un cours qu'il possède.
    if can_read_parcours(user, parcours):
        raise ParcoursCheckoutError("Accès déjà acquis.", 409)
    if not getattr(settings, "STRIPE_ENABLED", False):
        raise ParcoursCheckoutError("Paiement indisponible.", 503)
    if not waiver_accepted:
        raise ParcoursCheckoutError(WAIVER_ERROR, 400)

    amount_cents = int(round(parcours.prix * 100))
    stripe.api_key = settings.STRIPE_SECRET_KEY
    session = stripe.checkout.Session.create(
        mode="payment",
        line_items=[{
            "price_data": {
                "currency": "eur",
                "unit_amount": amount_cents,
                "product_data": {"name": f"Parcours « {parcours.titre} »"},
            },
            "quantity": 1,
        }],
        client_reference_id=str(user.pk),
        metadata={
            "kind": "parcours_access",
            "parcours_id": str(parcours.pk),
            "user_id": str(user.pk),
            "withdrawal_waiver": "accepted",
        },
        custom_text={"submit": {"message": STRIPE_SUBMIT_MESSAGE}},
        success_url=success_url,
        cancel_url=cancel_url,
    )

    ParcoursPayment.objects.create(
        user=user, parcours=parcours, provider="stripe",
        checkout_id=session.id, amount_eur=parcours.prix,
        waiver_accepted_at=timezone.now(),
    )
    return session


@login_required
@require_POST
def create_parcours_checkout(request, parcours_id):
    """Le serveur fixe le prix (celui du Parcours en base). CSRF Django et
    session utilisateur requis."""
    parcours = get_object_or_404(Parcours, id=parcours_id)
    status_url = request.build_absolute_uri(
        reverse("monetisation:parcours_checkout_status", args=[parcours.id])
    )
    try:
        session = create_parcours_checkout_session(
            request.user, parcours, status_url, status_url, waiver_accepted=waiver_from_request(request)
        )
    except ParcoursCheckoutError as exc:
        return JsonResponse({"error": str(exc)}, status=exc.status)
    except stripe.StripeError:
        logger.exception("Erreur de création Checkout Parcours")
        return JsonResponse({"error": "Impossible de créer le paiement."}, status=502)
    return JsonResponse({"url": session.url})


@login_required
def parcours_checkout_page(request, parcours_id):
    """Page web minimaliste : boutons Stripe et/ou PayPal."""
    parcours = get_object_or_404(Parcours, id=parcours_id)
    return render(request, "monetisation/parcours_checkout.html", {
        "parcours": parcours,
        "already_owned": can_read_parcours(request.user, parcours),
        "stripe_enabled": bool(getattr(settings, "STRIPE_ENABLED", False)),
        "paypal_enabled": bool(getattr(settings, "PAYPAL_CLIENT_ID", "")),
        "PAYPAL_CLIENT_ID": getattr(settings, "PAYPAL_CLIENT_ID", ""),
    })


@login_required
def parcours_checkout_status(request, parcours_id):
    """Page de retour informative ; jamais une preuve de paiement."""
    parcours = get_object_or_404(Parcours, id=parcours_id)
    acquired = can_read_parcours(request.user, parcours)
    return JsonResponse({"parcours_id": parcours.id, "access_active": acquired})


def create_parcours_paypal_order(user, parcours, waiver_accepted=False):
    """Cœur partagé web + mobile. Crée l'ordre PayPal (intent CAPTURE) et le
    ParcoursPayment 'pending' associé. Retourne le dict JSON de l'ordre créé.
    Lève ParcoursCheckoutError ou requests.RequestException."""
    if not parcours.is_published:
        raise ParcoursCheckoutError("Ce parcours n'est pas disponible.", 404)
    if not parcours.prix or parcours.prix <= 0:
        raise ParcoursCheckoutError("Ce parcours est gratuit.", 400)
    if can_read_parcours(user, parcours):
        raise ParcoursCheckoutError("Accès déjà acquis.", 409)
    if not getattr(settings, "PAYPAL_CLIENT_ID", ""):
        raise ParcoursCheckoutError("Paiement indisponible.", 503)
    if not waiver_accepted:
        raise ParcoursCheckoutError(WAIVER_ERROR, 400)

    url = f"{settings.PAYPAL_API_BASE}/v2/checkout/orders"
    auth = (settings.PAYPAL_CLIENT_ID, settings.PAYPAL_SECRET)
    custom_id = f"parcours|{parcours.id}|{user.id}"
    payload = {
        "intent": "CAPTURE",
        "purchase_units": [{
            "amount": {"currency_code": "EUR", "value": f"{parcours.prix:.2f}"},
            "custom_id": custom_id,
        }],
    }
    response = requests.post(url, json=payload, auth=auth, timeout=20)
    if response.status_code != 201:
        logger.error("PayPal a refusé la création de commande parcours : %s", response.text[:500])
        raise ParcoursCheckoutError("Impossible de créer la commande PayPal.", 502)
    order = response.json()

    ParcoursPayment.objects.create(
        user=user, parcours=parcours, provider="paypal",
        checkout_id=order["id"], amount_eur=parcours.prix,
        waiver_accepted_at=timezone.now(),
    )
    return order


def capture_parcours_paypal_order(user, order_id):
    """Cœur partagé web + mobile. Capture un ordre PayPal pour un parcours et
    accorde l'accès si tout correspond (montant, devise, propriétaire).
    Retourne le ParcoursAccess accordé. Lève ParcoursCheckoutError."""
    with transaction.atomic():
        payment = ParcoursPayment.objects.select_for_update().filter(
            checkout_id=order_id, provider="paypal"
        ).first()
        if payment is None:
            raise ParcoursCheckoutError("Commande inconnue.", 400)
        if payment.user_id != user.id:
            raise ParcoursCheckoutError("Cette commande n'appartient pas à cet utilisateur.", 403)
        if payment.status != "pending":
            existing = ParcoursAccess.objects.filter(user=user, parcours_id=payment.parcours_id).first()
            if existing is None:
                raise ParcoursCheckoutError("Commande déjà traitée.", 409)
            return existing

        url = f"{settings.PAYPAL_API_BASE}/v2/checkout/orders/{order_id}/capture"
        auth = (settings.PAYPAL_CLIENT_ID, settings.PAYPAL_SECRET)
        try:
            response = requests.post(url, auth=auth, timeout=20)
            result = response.json()
        except (requests.RequestException, ValueError):
            raise ParcoursCheckoutError("PayPal est injoignable, réessayez.", 502)

        if result.get("status") != "COMPLETED":
            raise ParcoursCheckoutError("Paiement non complété.", 400)

        try:
            purchase_unit = result["purchase_units"][0]
            capture = purchase_unit["payments"]["captures"][0]
            currency = capture["amount"]["currency_code"]
            captured_amount = Decimal(capture["amount"]["value"])
            capture_id = capture.get("id", "")
        except (KeyError, IndexError, TypeError, ValueError):
            raise ParcoursCheckoutError("Réponse PayPal inattendue.", 400)

        custom_id = purchase_unit.get("custom_id", "")
        parts = custom_id.split("|")
        valid_custom_id = (
            len(parts) == 3 and parts[0] == "parcours"
            and parts[1] == str(payment.parcours_id) and parts[2] == str(user.id)
        )
        if not valid_custom_id:
            logger.warning("Commande PayPal parcours invalide (custom_id=%s)", custom_id)
            raise ParcoursCheckoutError("Commande PayPal invalide.", 400)
        if currency != "EUR" or captured_amount < payment.amount_eur:
            raise ParcoursCheckoutError("Montant ou devise inattendu.", 400)

        access, _ = ParcoursAccess.objects.update_or_create(
            user=user, parcours_id=payment.parcours_id,
            defaults={
                "provider": "paypal",
                "payment_reference": capture_id,
                "amount_eur": payment.amount_eur,
                "active": True,
                "revoked_at": None,
            },
        )
        payment.payment_reference = capture_id
        payment.status = "success"
        payment.save(update_fields=["payment_reference", "status"])
        return access


@login_required
@require_POST
def create_parcours_paypal_order_view(request, parcours_id):
    parcours = get_object_or_404(Parcours, id=parcours_id)
    try:
        order = create_parcours_paypal_order(
            request.user, parcours, waiver_accepted=waiver_from_request(request)
        )
    except ParcoursCheckoutError as exc:
        return JsonResponse({"error": str(exc)}, status=exc.status)
    except requests.RequestException:
        logger.exception("PayPal injoignable (création de commande parcours)")
        return JsonResponse({"error": "PayPal est injoignable, réessayez."}, status=502)
    return JsonResponse(order)


@login_required
@require_POST
def capture_parcours_paypal_order_view(request, parcours_id):
    import json
    try:
        data = json.loads(request.body) if request.body else {}
    except ValueError:
        data = {}
    order_id = data.get("order_id")
    if not order_id:
        return JsonResponse({"error": "order_id requis"}, status=400)
    try:
        capture_parcours_paypal_order(request.user, order_id)
    except ParcoursCheckoutError as exc:
        return JsonResponse({"error": str(exc)}, status=exc.status)
    return JsonResponse({"success": True})


def handle_parcours_stripe_event(event_type, session):
    """Appelé uniquement après vérification de la signature du webhook commun."""
    session_id = session.get("id")
    if not session_id:
        return
    with transaction.atomic():
        payment = ParcoursPayment.objects.select_for_update().filter(
            checkout_id=session_id, provider="stripe"
        ).first()
        if payment is None or payment.status != "pending":
            return
        if event_type == "checkout.session.expired":
            payment.status = "failed"
            payment.save(update_fields=["status"])
            return
        metadata = session.get("metadata") or {}
        expected_cents = int(round(payment.amount_eur * 100))
        if (
            event_type != "checkout.session.completed"
            or session.get("payment_status") != "paid"
            or session.get("mode") != "payment"
            or session.get("currency") != "eur"
            or session.get("amount_total") != expected_cents
            or metadata.get("kind") != "parcours_access"
            or metadata.get("parcours_id") != str(payment.parcours_id)
            or metadata.get("user_id") != str(payment.user_id)
            or str(session.get("client_reference_id")) != str(payment.user_id)
        ):
            logger.warning("Checkout Parcours invalide: %s", session_id)
            return
        ParcoursAccess.objects.update_or_create(
            user=payment.user, parcours_id=payment.parcours_id,
            defaults={
                "provider": "stripe",
                "payment_reference": session.get("payment_intent") or session_id,
                "amount_eur": payment.amount_eur,
                "active": True,
                "revoked_at": None,
            },
        )
        payment.payment_reference = session.get("payment_intent") or ""
        payment.status = "success"
        payment.save(update_fields=["payment_reference", "status"])
