"""Paiement par carte (Stripe) pour les commandes du shop FOUNATEK.

Règle de devise : la carte n'est proposée que si le client voit ses prix en
euros (EUR) ou en dollars (USD) — il est alors débité dans cette devise, au
taux ExchangeRate affiché sur le site. En GNF (ou autre devise), le client
passe par le paiement manuel (Orange Money, MTN MoMo, espèces).

Cycle de vie d'une commande payée par carte :
- création : la commande est enregistrée, les points de fidélité utilisés
  pour la remise sont réservés (débités tout de suite), le stock ne bouge pas ;
- paiement confirmé (webhook checkout.session.completed) : stock décrémenté,
  points gagnés attribués, commande confirmée, e-mails envoyés ;
- abandon : le client peut relancer le paiement ou annuler depuis la page de
  sa commande ; si la session Stripe expire (1 h), la commande est annulée
  automatiquement (webhook checkout.session.expired) et les points réservés
  sont rendus.

Le webhook unique du projet (monetisation.stripe_payments.stripe_webhook)
route ici les événements dont metadata.kind == "shop_order".
"""
import logging
import time

import stripe
from django.conf import settings
from django.db import transaction

logger = logging.getLogger(__name__)

# Devises dans lesquelles la carte est proposée.
CARD_CURRENCIES = ("EUR", "USD")
# Minimum accepté par Stripe : 0,50 EUR / 0,50 USD.
MIN_CHARGE_CENTS = 50
# Une session non payée expire au bout d'1 h (Stripe impose 30 min à 24 h) :
# la commande abandonnée est alors annulée automatiquement.
SESSION_LIFETIME_SECONDS = 60 * 60

CARD_ONLY_EUR_USD_MESSAGE = (
    "Le paiement par carte est possible uniquement quand les prix sont affichés "
    "en euros (EUR) ou en dollars (USD). Sinon, choisissez le paiement manuel "
    "(Orange Money, MTN MoMo ou espèces) : l'équipe confirme votre paiement "
    "après la commande."
)
CARD_DISABLED_MESSAGE = "Le paiement par carte n'est pas disponible pour le moment."
ALREADY_PAID_MESSAGE = (
    "Le paiement de cette commande a déjà été effectué : il est en cours de "
    "confirmation, actualisez la page dans quelques secondes."
)


class CardPaymentError(Exception):
    """Problème à afficher tel quel au client (pas une erreur technique)."""


def stripe_enabled():
    return bool(getattr(settings, "STRIPE_ENABLED", False))


def card_rate(currency_code):
    """Taux 1 GNF -> X <devise> pour la carte, ou None si la carte n'est pas
    possible dans cette devise (devise hors EUR/USD ou taux non configuré)."""
    from .models import ExchangeRate

    code = (currency_code or "").upper()
    if code not in CARD_CURRENCIES:
        return None
    rate = ExchangeRate.objects.filter(currency_code=code).first()
    if rate and rate.rate_from_gnf and rate.rate_from_gnf > 0:
        return float(rate.rate_from_gnf)
    return None


def card_availability(currency_code):
    """(disponible, message) — sert à afficher l'option carte et à valider le
    choix du client côté serveur."""
    if not stripe_enabled():
        return False, CARD_DISABLED_MESSAGE
    if card_rate(currency_code) is None:
        return False, CARD_ONLY_EUR_USD_MESSAGE
    return True, ""


def _stripe():
    stripe.api_key = settings.STRIPE_SECRET_KEY
    return stripe


def create_order_checkout_session(order, currency_code, success_url, cancel_url):
    """Crée (ou recrée, si le client relance le paiement) la session Stripe
    Checkout d'une commande déjà enregistrée avec ses articles.

    Lève CardPaymentError (message pour le client) ou stripe.StripeError."""
    available, message = card_availability(currency_code)
    if not available:
        raise CardPaymentError(message)

    rate = card_rate(currency_code)
    cents = int(round(float(order.total) * rate * 100))
    if cents < MIN_CHARGE_CENTS:
        raise CardPaymentError(
            "Montant trop faible pour un paiement par carte (minimum 0,50 EUR ou "
            "0,50 USD). Choisissez le paiement manuel."
        )
    currency = currency_code.lower()
    api = _stripe()

    # Paiement relancé : l'ancienne session ne doit plus pouvoir être payée.
    previous = None
    if order.stripe_session_id:
        previous = api.checkout.Session.retrieve(order.stripe_session_id)
        if previous.status == "complete":
            raise CardPaymentError(ALREADY_PAID_MESSAGE)

    session = api.checkout.Session.create(
        mode="payment",
        line_items=[{
            "price_data": {
                "currency": currency,
                "unit_amount": cents,
                "product_data": {"name": f"Commande FOUNATEK #{order.pk}"},
            },
            "quantity": 1,
        }],
        client_reference_id=str(order.user_id),
        metadata={
            "kind": "shop_order",
            "order_id": str(order.pk),
            "user_id": str(order.user_id),
        },
        expires_at=int(time.time()) + SESSION_LIFETIME_SECONDS,
        success_url=success_url,
        cancel_url=cancel_url,
    )

    order.stripe_session_id = session.id
    order.card_currency = currency
    order.card_amount_cents = cents
    order.save(update_fields=["stripe_session_id", "card_currency", "card_amount_cents"])

    # Expirée APRÈS l'enregistrement de la nouvelle session : l'événement
    # « expired » de l'ancienne ne correspond plus à la commande et sera ignoré.
    if previous is not None and previous.status == "open":
        try:
            api.checkout.Session.expire(previous.id)
        except stripe.StripeError:
            logger.warning("Impossible d'expirer l'ancienne session %s (commande #%s)", previous.id, order.pk)

    return session


def _cancel_unpaid_card_order(order):
    """Annule une commande carte non payée et rend les points réservés.
    Retourne True si la commande vient d'être annulée."""
    from .models import LoyaltyAccount

    if order.payment_method != "card" or order.payment_status != "pending" or order.status != "pending":
        return False
    if order.pending_points_used:
        loyalty, _ = LoyaltyAccount.objects.get_or_create(user=order.user)
        loyalty.refund_points(order.pending_points_used, order)
    order.status = "cancelled"
    order.payment_status = "failed"
    order.pending_points_used = 0
    order.save(update_fields=["status", "payment_status", "pending_points_used"])
    return True


def _restore_cart(order):
    """Remet les articles d'une commande annulée dans le panier du client."""
    from .models import Cart, CartItem

    cart, _ = Cart.objects.get_or_create(user=order.user)
    for item in order.items.select_related("product"):
        if not item.product.is_active:
            continue
        cart_item, created = CartItem.objects.get_or_create(cart=cart, product=item.product)
        cart_item.quantity = item.quantity if created else cart_item.quantity + item.quantity
        cart_item.save()


def cancel_card_order_by_customer(order):
    """Le client abandonne le paiement carte depuis la page de sa commande :
    annule la commande, rend les points, remet les articles dans le panier
    et désactive la session Stripe. Lève CardPaymentError si elle est déjà payée."""
    from .models import Order

    api = _stripe()
    current = None
    if order.stripe_session_id:
        current = api.checkout.Session.retrieve(order.stripe_session_id)
        if current.status == "complete":
            raise CardPaymentError(ALREADY_PAID_MESSAGE)

    with transaction.atomic():
        locked = Order.objects.select_for_update().get(pk=order.pk)
        cancelled = _cancel_unpaid_card_order(locked)
        if cancelled:
            _restore_cart(locked)

    if current is not None and current.status == "open":
        try:
            api.checkout.Session.expire(current.id)
        except stripe.StripeError:
            logger.warning("Impossible d'expirer la session %s (commande #%s)", current.id, order.pk)
    return cancelled


def handle_shop_order_expired(session):
    """Webhook checkout.session.expired : le client n'a jamais payé."""
    from .models import Order

    with transaction.atomic():
        order = Order.objects.select_for_update().filter(stripe_session_id=session.get("id")).first()
        if order is not None:
            _cancel_unpaid_card_order(order)


def handle_shop_order_paid(session):
    """Webhook checkout.session.completed (payment_status == "paid", vérifié
    par l'appelant). `session` est un dict Python (to_dict())."""
    from .models import Order, Product, LoyaltyAccount
    from .signals import send_order_email, send_admin_order_notification, send_admin_alert

    session_id = session.get("id")
    metadata = session.get("metadata") or {}
    amount_total = session.get("amount_total")
    currency = (session.get("currency") or "").lower()
    paid_label = f"{(amount_total or 0) / 100:.2f} {currency.upper()}"

    with transaction.atomic():
        order = Order.objects.select_for_update().filter(stripe_session_id=session_id).first()

        if order is None:
            logger.error("Paiement Stripe %s sans commande correspondante (commande #%s)", session_id, metadata.get("order_id"))
            transaction.on_commit(lambda: send_admin_alert(
                "Paiement carte à vérifier",
                f"Stripe a confirmé un paiement de {paid_label} (session {session_id}) pour la "
                f"commande #{metadata.get('order_id')}, mais aucune commande n'attend ce paiement.\n"
                f"Vérifie dans Stripe et rembourse le client si besoin.",
            ))
            return

        if order.payment_status == "paid":
            return  # Stripe peut redélivrer le même événement.

        if order.status == "cancelled":
            logger.error("Paiement Stripe reçu pour la commande annulée #%s", order.pk)
            transaction.on_commit(lambda: send_admin_alert(
                f"Paiement reçu pour la commande annulée #{order.pk}",
                f"Le client a payé {paid_label} par carte alors que la commande #{order.pk} "
                f"était annulée. Rembourse-le depuis Stripe ou réactive la commande.",
            ))
            return

        if currency != order.card_currency or amount_total != order.card_amount_cents:
            logger.warning(
                "Webhook Stripe (shop) : montant inattendu pour la commande #%s (attendu %s %s, reçu %s %s)",
                order.pk, order.card_amount_cents, order.card_currency, amount_total, currency,
            )
            order.payment_status = "failed"
            order.save(update_fields=["payment_status"])
            transaction.on_commit(lambda: send_admin_alert(
                f"Montant carte incohérent — commande #{order.pk}",
                f"Stripe a encaissé {paid_label} au lieu de {(order.card_amount_cents or 0) / 100:.2f} "
                f"{order.card_currency.upper()}. Commande marquée « paiement échoué » : vérifie dans Stripe.",
            ))
            return

        # Stock : produits verrouillés pour que deux paiements simultanés ne
        # s'écrasent pas ; un manque de stock est signalé à l'admin (le client
        # a déjà payé, la commande reste confirmée).
        shortages = []
        for item in order.items.all():
            product = Product.objects.select_for_update().get(pk=item.product_id)
            if product.stock < item.quantity:
                shortages.append(f"- {product.name} : {item.quantity} commandé(s), {product.stock} en stock")
            product.stock = max(0, product.stock - item.quantity)
            product.save(update_fields=["stock"])

        loyalty, _ = LoyaltyAccount.objects.get_or_create(user=order.user)
        earned = loyalty.add_points(order)

        order.payment_status = "paid"
        order.status = "confirmed"
        order.save(update_fields=["payment_status", "status"])

        def _notify():
            # Après validation en base : un envoi lent ne retarde pas la
            # réponse à Stripe et ne garde aucune ligne verrouillée.
            send_order_email(order, earned, loyalty)
            send_admin_order_notification(order)
            if shortages:
                send_admin_alert(
                    f"Stock insuffisant — commande #{order.pk} payée par carte",
                    "La commande a été payée mais le stock ne suffit pas :\n" + "\n".join(shortages)
                    + "\n\nContacte le client (délai ou remboursement depuis Stripe).",
                )

        transaction.on_commit(_notify)
