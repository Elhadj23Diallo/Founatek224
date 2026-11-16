"""Tests pour le paiement par carte (Stripe) du shop FOUNATEK.

Contrairement à cash/Orange Money/MTN MoMo (stock + points immédiats), la
carte doit différer stock et points jusqu'à la confirmation du webhook.
Aucun appel réseau réel : stripe.checkout.Session.create et
stripe.Webhook.construct_event sont mockés.
"""
import json
from unittest.mock import patch, Mock

import stripe
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from .models import Category, Product, Cart, CartItem, Order, LoyaltyAccount

User = get_user_model()


def _completed_shop_event(session_id, order_id, user_id, amount_cents, currency="eur", metadata_amount_cents=None):
    if metadata_amount_cents is None:
        metadata_amount_cents = amount_cents
    return stripe.Event.construct_from({
        "id": "evt_shop_1",
        "object": "event",
        "type": "checkout.session.completed",
        "data": {"object": {
            "id": session_id,
            "object": "checkout.session",
            "payment_status": "paid",
            "amount_total": amount_cents,
            "currency": currency,
            "metadata": {
                "user_id": str(user_id),
                "order_id": str(order_id),
                "amount_cents": str(metadata_amount_cents),
                "kind": "shop_order",
            },
        }},
    }, "sk_test_dummy")


@override_settings(STRIPE_SECRET_KEY="sk_test_fake", STRIPE_WEBHOOK_SECRET="whsec_fake", STRIPE_ENABLED=True)
class ShopCardCheckoutWebTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="shop-card-user", password="pass")
        self.client.force_login(self.user)
        category = Category.objects.create(name="Capteurs", slug="capteurs-card")
        self.product = Product.objects.create(
            name="Capteur Card", slug="capteur-card", category=category, price=25000, stock=5,
        )
        cart = Cart.objects.create(user=self.user)
        CartItem.objects.create(cart=cart, product=self.product, quantity=2)

    @patch("founatekapp.stripe_checkout.stripe.checkout.Session.create")
    def test_card_checkout_defers_stock_and_redirects_to_stripe(self, mock_create):
        mock_create.return_value = Mock(id="cs_shop_1", url="https://checkout.stripe.com/pay/cs_shop_1")

        resp = self.client.post("/shop/commander/", {
            "address": "Conakry",
            "phone": "+224600000000",
            "payment_method": "card",
        })

        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, "https://checkout.stripe.com/pay/cs_shop_1")

        order = Order.objects.get(user=self.user)
        self.assertEqual(order.payment_method, "card")
        self.assertEqual(order.payment_status, "pending")
        self.assertEqual(order.stripe_session_id, "cs_shop_1")

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 5, "le stock ne doit pas bouger avant confirmation du paiement")
        self.assertFalse(LoyaltyAccount.objects.filter(user=self.user, points__gt=0).exists())

    def test_card_checkout_unavailable_when_stripe_not_configured(self):
        with self.settings(STRIPE_ENABLED=False):
            resp = self.client.post("/shop/commander/", {
                "address": "Conakry",
                "phone": "+224600000000",
                "payment_method": "card",
            })
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(Order.objects.filter(user=self.user).exists())


@override_settings(STRIPE_SECRET_KEY="sk_test_fake", STRIPE_WEBHOOK_SECRET="whsec_fake", STRIPE_ENABLED=True)
class ShopCardCheckoutMobileTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="shop-card-mobile", password="pass")
        self.token, _ = Token.objects.get_or_create(user=self.user)
        self.api_client = APIClient()
        self.api_client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")
        category = Category.objects.create(name="Capteurs", slug="capteurs-card-mobile")
        self.product = Product.objects.create(
            name="Capteur Card Mobile", slug="capteur-card-mobile", category=category, price=25000, stock=5,
        )
        cart = Cart.objects.create(user=self.user)
        CartItem.objects.create(cart=cart, product=self.product, quantity=1)

    @patch("founatekapp.stripe_checkout.stripe.checkout.Session.create")
    def test_mobile_checkout_card_returns_checkout_url(self, mock_create):
        mock_create.return_value = Mock(id="cs_shop_mobile_1", url="https://checkout.stripe.com/pay/cs_shop_mobile_1")

        resp = self.api_client.post("/api/v1/orders/checkout/", {
            "shipping_address": "Conakry",
            "phone": "+224600000000",
            "payment_method": "card",
        }, format="json")

        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.json()["url"], "https://checkout.stripe.com/pay/cs_shop_mobile_1")
        order = Order.objects.get(user=self.user)
        self.assertEqual(order.payment_status, "pending")
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 5)


@override_settings(STRIPE_SECRET_KEY="sk_test_fake", STRIPE_WEBHOOK_SECRET="whsec_fake", STRIPE_ENABLED=True)
class ShopStripeWebhookTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="shop-webhook-user", password="pass")
        category = Category.objects.create(name="Capteurs", slug="capteurs-webhook")
        self.product = Product.objects.create(
            name="Capteur Webhook", slug="capteur-webhook", category=category, price=25000, stock=5,
        )
        self.order = Order.objects.create(
            user=self.user, shipping_address="Conakry", phone="+224600000000",
            payment_method="card", payment_status="pending", stripe_session_id="cs_shop_evt_1",
        )
        from .models import OrderItem
        OrderItem.objects.create(order=self.order, product=self.product, quantity=2, unit_price=self.product.price)
        # order.total = 50000 GNF ; avec le taux de secours (1/10000 EUR/GNF) -> 5.00 EUR -> 500 centimes.
        self.amount_cents = 500

    @patch("monetisation.stripe_payments.stripe.Webhook.construct_event")
    def test_webhook_confirms_order_and_applies_stock_and_points(self, mock_construct):
        mock_construct.return_value = _completed_shop_event(
            "cs_shop_evt_1", self.order.pk, self.user.id, self.amount_cents,
        )

        resp = self.client.post(
            "/monetisation/stripe/webhook/", data="{}",
            content_type="application/json", HTTP_STRIPE_SIGNATURE="good-sig",
        )

        self.assertEqual(resp.status_code, 200)
        self.order.refresh_from_db()
        self.assertEqual(self.order.payment_status, "paid")
        self.assertEqual(self.order.status, "confirmed")

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 3)

        loyalty = LoyaltyAccount.objects.get(user=self.user)
        self.assertGreater(loyalty.points, 0)

    @patch("monetisation.stripe_payments.stripe.Webhook.construct_event")
    def test_webhook_delivered_twice_applies_stock_only_once(self, mock_construct):
        mock_construct.return_value = _completed_shop_event(
            "cs_shop_evt_1", self.order.pk, self.user.id, self.amount_cents,
        )

        self.client.post("/monetisation/stripe/webhook/", data="{}", content_type="application/json", HTTP_STRIPE_SIGNATURE="good-sig")
        self.client.post("/monetisation/stripe/webhook/", data="{}", content_type="application/json", HTTP_STRIPE_SIGNATURE="good-sig")

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 3, "le stock ne doit être décrémenté qu'une seule fois")

    @patch("monetisation.stripe_payments.stripe.Webhook.construct_event")
    def test_webhook_amount_mismatch_does_not_confirm_order(self, mock_construct):
        mock_construct.return_value = _completed_shop_event(
            "cs_shop_evt_1", self.order.pk, self.user.id,
            amount_cents=100, metadata_amount_cents=self.amount_cents,  # Stripe dit avoir encaisse moins que prevu
        )

        resp = self.client.post(
            "/monetisation/stripe/webhook/", data="{}",
            content_type="application/json", HTTP_STRIPE_SIGNATURE="good-sig",
        )

        self.assertEqual(resp.status_code, 200)
        self.order.refresh_from_db()
        self.assertEqual(self.order.payment_status, "failed")
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 5, "pas de décrément de stock si le montant ne correspond pas")
