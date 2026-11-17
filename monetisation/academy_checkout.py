"""Achat unique du Livre 1 par Stripe, indépendant des recharges wallet."""
import logging

import stripe
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse
from django.urls import reverse
from django.views.decorators.http import require_POST

from iot.book_catalog import BOOK_SLUG, PACK_PRICE_EUR
from iot.models import AcademyPackAccess, AcademyPackPayment, AcademyBookLesson

logger = logging.getLogger(__name__)


@login_required
@require_POST
def create_academy_checkout(request):
    """Le serveur fixe le prix. CSRF Django et session utilisateur requis."""
    if not getattr(settings, "ACADEMY_BOOK_CHECKOUT_ENABLED", False):
        return JsonResponse({"error": "Les achats Academy ne sont pas encore ouverts."}, status=503)
    if not AcademyBookLesson.objects.filter(published=True).exclude(chapter_number="00").exists():
        return JsonResponse({"error": "Le pack payant n’est pas encore disponible."}, status=503)
    if not getattr(settings, "STRIPE_ENABLED", False):
        return JsonResponse({"error": "Paiement indisponible."}, status=503)
    if AcademyPackAccess.objects.filter(
        user=request.user, pack_slug=BOOK_SLUG, active=True, revoked_at__isnull=True
    ).exists():
        return JsonResponse({"error": "Pack déjà acquis."}, status=409)

    stripe.api_key = settings.STRIPE_SECRET_KEY
    try:
        session = stripe.checkout.Session.create(
            mode="payment",
            line_items=[{
                "price_data": {
                    "currency": "eur",
                    "unit_amount": 999,
                    "product_data": {"name": "Founatek Academy — Livre 1 (chapitres 01 à 11)"},
                },
                "quantity": 1,
            }],
            client_reference_id=str(request.user.pk),
            metadata={"kind": "academy_book_pack", "pack_slug": BOOK_SLUG, "user_id": str(request.user.pk)},
            success_url=request.build_absolute_uri(reverse("monetisation:academy_checkout_status")),
            cancel_url=request.build_absolute_uri(reverse("monetisation:academy_checkout_status")),
        )
    except stripe.StripeError:
        logger.exception("Erreur de création Checkout Academy")
        return JsonResponse({"error": "Impossible de créer le paiement."}, status=502)

    AcademyPackPayment.objects.create(
        user=request.user, pack_slug=BOOK_SLUG, provider="stripe",
        checkout_id=session.id, amount_eur=PACK_PRICE_EUR,
    )
    return JsonResponse({"url": session.url})


@login_required
def academy_checkout_status(request):
    """Page de retour informative; jamais une preuve de paiement."""
    acquired = AcademyPackAccess.objects.filter(
        user=request.user, pack_slug=BOOK_SLUG, active=True, revoked_at__isnull=True
    ).exists()
    return JsonResponse({"pack": BOOK_SLUG, "access_active": acquired})


def handle_academy_stripe_event(event_type, session):
    """Appelé uniquement après vérification de la signature du webhook commun."""
    session_id = session.get("id")
    if not session_id:
        return
    with transaction.atomic():
        payment = AcademyPackPayment.objects.select_for_update().filter(
            checkout_id=session_id, provider="stripe", pack_slug=BOOK_SLUG
        ).first()
        if payment is None or payment.status != "pending":
            return
        if event_type == "checkout.session.expired":
            payment.status = "failed"
            payment.save(update_fields=["status"])
            return
        metadata = session.get("metadata") or {}
        if (
            event_type != "checkout.session.completed"
            or session.get("payment_status") != "paid"
            or session.get("mode") != "payment"
            or session.get("currency") != "eur"
            or session.get("amount_total") != 999
            or payment.amount_eur != PACK_PRICE_EUR
            or metadata.get("kind") != "academy_book_pack"
            or metadata.get("pack_slug") != BOOK_SLUG
            or metadata.get("user_id") != str(payment.user_id)
            or str(session.get("client_reference_id")) != str(payment.user_id)
        ):
            logger.warning("Checkout Academy invalide: %s", session_id)
            return
        AcademyPackAccess.objects.update_or_create(
            user=payment.user, pack_slug=BOOK_SLUG,
            defaults={
                "provider": "stripe",
                "payment_reference": session.get("payment_intent") or session_id,
                "amount_eur": PACK_PRICE_EUR,
                "active": True,
                "revoked_at": None,
            },
        )
        payment.payment_reference = session.get("payment_intent") or ""
        payment.status = "success"
        payment.save(update_fields=["payment_reference", "status"])
