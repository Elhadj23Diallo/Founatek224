"""Paiement par carte (Stripe) pour les commandes du shop FOUNATEK.

Les prix du shop sont en GNF ; Stripe ne règle pas directement en GNF, donc le
montant facturé est l'équivalent EUR (même conversion que la recharge wallet
par Mobile Money : monetisation.utils.gnf_to_eur).

Contrairement à cash/Orange Money/MTN MoMo — où la commande est créée, le
stock décrémenté et les points de fidélité attribués immédiatement, le
paiement étant vérifié après, à la main — pour la carte le stock et les
points ne sont attribués QUE quand le webhook Stripe confirme le paiement
(voir monetisation.stripe_payments.stripe_webhook, qui route ici les
événements dont metadata.kind == "shop_order").
"""
import logging

import stripe
from django.conf import settings
from django.db import transaction

from monetisation.utils import gnf_to_eur

logger = logging.getLogger(__name__)

# Stripe refuse un montant sous environ 0.50 EUR : plancher de sécurité.
MIN_CHARGE_CENTS = 50


def create_order_checkout_session(order, success_url, cancel_url):
    """Crée la session Stripe Checkout pour une commande déjà créée (ses
    OrderItem sont déjà attachés, le stock n'est pas encore décrémenté).
    Retourne la Session Stripe. Lève stripe.StripeError si Stripe échoue."""
    amount_eur = gnf_to_eur(order.total)
    cents = max(MIN_CHARGE_CENTS, int(round(amount_eur * 100)))

    stripe.api_key = settings.STRIPE_SECRET_KEY
    session = stripe.checkout.Session.create(
        mode="payment",
        line_items=[{
            "price_data": {
                "currency": "eur",
                "unit_amount": cents,
                "product_data": {"name": f"Commande FOUNATEK #{order.pk}"},
            },
            "quantity": 1,
        }],
        client_reference_id=str(order.user_id),
        metadata={
            "user_id": str(order.user_id),
            "order_id": str(order.pk),
            "amount_cents": str(cents),
            "kind": "shop_order",
        },
        success_url=success_url,
        cancel_url=cancel_url,
    )

    order.stripe_session_id = session.id
    order.save(update_fields=["stripe_session_id"])
    return session


def handle_shop_order_webhook_event(session):
    """Appelé par monetisation.stripe_payments.stripe_webhook quand
    metadata.kind == "shop_order". `session` est déjà un dict Python (via
    .to_dict()), au statut payment_status == "paid" confirmé par l'appelant.

    Décrémente le stock, attribue les points de fidélité gagnés, débite les
    points éventuellement utilisés pour la remise, et marque la commande
    payée/confirmée — tout ce que le checkout "carte" avait volontairement
    différé par rapport à cash/Mobile Money."""
    from .models import Order, LoyaltyAccount

    session_id = session.get("id")

    with transaction.atomic():
        try:
            order = Order.objects.select_for_update().get(stripe_session_id=session_id)
        except Order.DoesNotExist:
            logger.warning("Webhook Stripe (shop) pour une session inconnue: %s", session_id)
            return

        if order.payment_status == "paid":
            # Déjà traité : Stripe peut redélivrer le même événement.
            return

        amount_total = session.get("amount_total")
        currency = session.get("currency")
        expected_cents = int((session.get("metadata") or {}).get("amount_cents", 0))

        if currency != "eur" or amount_total != expected_cents:
            logger.warning(
                "Webhook Stripe (shop): montant/devise inattendus pour la commande #%s (session %s)",
                order.pk, session_id,
            )
            order.payment_status = "failed"
            order.save(update_fields=["payment_status"])
            return

        for item in order.items.select_related("product"):
            p = item.product
            p.stock = max(0, p.stock - item.quantity)
            p.save(update_fields=["stock"])

        loyalty, _ = LoyaltyAccount.objects.get_or_create(user=order.user)
        earned = loyalty.add_points(order)

        if order.pending_points_used > 0:
            try:
                loyalty.use_points(order.pending_points_used, order)
            except ValueError:
                # Points plus disponibles (rare, p.ex. déjà dépensés ailleurs) :
                # la remise reste appliquée sur la commande, pas de nouvelle erreur.
                pass

        order.payment_status = "paid"
        order.status = "confirmed"
        order.save(update_fields=["payment_status", "status"])

        from .signals import send_order_email, send_admin_order_notification
        send_order_email(order, earned, loyalty)
        send_admin_order_notification(order)
