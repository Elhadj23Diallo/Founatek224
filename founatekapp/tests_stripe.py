"""Tests du paiement par carte (Stripe) du shop FOUNATEK.

- la carte n'est proposée que si les prix sont affichés en EUR ou USD ;
- stock différé jusqu'au paiement, points réservés dès la commande ;
- le client peut relancer le paiement ou annuler (articles remis au panier) ;
- webhook : confirmation, idempotence, montant incohérent, expiration,
  paiement sur commande annulée, stock insuffisant.
Aucun appel réseau : les appels Stripe sont mockés.
"""
from unittest.mock import patch, Mock

import stripe
from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from .models import (
    Category, Product, Cart, CartItem, Order, OrderItem, LoyaltyAccount,
    ExchangeRate, CurrencyPreference,
)

User = get_user_model()

STRIPE_SETTINGS = dict(STRIPE_SECRET_KEY="sk_test_fake", STRIPE_WEBHOOK_SECRET="whsec_fake", STRIPE_ENABLED=True)
SESSION_CREATE = "founatekapp.stripe_checkout.stripe.checkout.Session.create"
SESSION_RETRIEVE = "founatekapp.stripe_checkout.stripe.checkout.Session.retrieve"
SESSION_EXPIRE = "founatekapp.stripe_checkout.stripe.checkout.Session.expire"
CONSTRUCT_EVENT = "monetisation.stripe_payments.stripe.Webhook.construct_event"


def _shop_event(session_id, amount_cents, currency="eur", event_type="checkout.session.completed",
                payment_status="paid", order_id=1):
    return stripe.Event.construct_from({
        "id": "evt_shop_1",
        "object": "event",
        "type": event_type,
        "data": {"object": {
            "id": session_id,
            "object": "checkout.session",
            "payment_status": payment_status,
            "amount_total": amount_cents,
            "currency": currency,
            "metadata": {"kind": "shop_order", "order_id": str(order_id), "user_id": "1"},
        }},
    }, "sk_test_dummy")


def _rates():
    # 1 EUR = 10 000 GNF ; 1 USD ≈ 8 700 GNF
    ExchangeRate.objects.create(currency_code="EUR", currency_symbol="€", rate_from_gnf="0.000100")
    ExchangeRate.objects.create(currency_code="USD", currency_symbol="$", rate_from_gnf="0.000115")


@override_settings(**STRIPE_SETTINGS)
class ShopCardCheckoutWebTest(TestCase):
    def setUp(self):
        _rates()
        self.user = User.objects.create_user(username="shop-card-user", password="pass", email="client@example.com")
        self.client.force_login(self.user)
        category = Category.objects.create(name="Capteurs", slug="capteurs-card")
        self.product = Product.objects.create(
            name="Capteur Card", slug="capteur-card", category=category, price=25000, stock=5,
        )
        self.cart = Cart.objects.create(user=self.user)
        CartItem.objects.create(cart=self.cart, product=self.product, quantity=2)  # 50 000 GNF

    def _currency(self, code):
        session = self.client.session
        session["currency_code"] = code
        session.save()

    def _post_card(self, **extra):
        data = {"address": "Conakry", "phone": "+224600000000", "payment_method": "card"}
        data.update(extra)
        return self.client.post("/shop/commander/", data)

    # --- Affichage de la page /shop/commander/ -------------------------------
    def test_checkout_page_offers_card_when_prices_in_eur(self):
        self._currency("EUR")
        resp = self.client.get("/shop/commander/")
        self.assertTrue(resp.context["card_available"])
        self.assertContains(resp, 'value="card" class="form-check-input me-2">')

    def test_checkout_page_in_gnf_explains_card_needs_eur_or_usd(self):
        resp = self.client.get("/shop/commander/")
        self.assertFalse(resp.context["card_available"])
        self.assertContains(resp, "uniquement quand les prix sont affichés")
        self.assertContains(resp, "Orange Money")
        self.assertContains(resp, 'form="switch-currency-EUR"')
        self.assertContains(resp, "disabled")

    def test_no_card_option_when_stripe_not_configured(self):
        self._currency("EUR")
        with self.settings(STRIPE_ENABLED=False):
            resp = self.client.get("/shop/commander/")
            self.assertNotContains(resp, 'value="card"')
            post = self._post_card()
        self.assertEqual(post.status_code, 200)
        self.assertFalse(Order.objects.exists())

    # --- Commande par carte ------------------------------------------------
    @patch(SESSION_CREATE)
    def test_card_checkout_in_eur_charges_eur_and_defers_stock(self, mock_create):
        self._currency("EUR")
        mock_create.return_value = Mock(id="cs_shop_1", url="https://checkout.stripe.com/pay/cs_shop_1")

        resp = self._post_card()

        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, "https://checkout.stripe.com/pay/cs_shop_1")
        kwargs = mock_create.call_args.kwargs
        self.assertEqual(kwargs["line_items"][0]["price_data"]["currency"], "eur")
        self.assertEqual(kwargs["line_items"][0]["price_data"]["unit_amount"], 500)
        self.assertIn("expires_at", kwargs)
        self.assertIn("?paiement=annule", kwargs["cancel_url"])

        order = Order.objects.get(user=self.user)
        self.assertEqual((order.payment_method, order.payment_status), ("card", "pending"))
        self.assertEqual((order.card_currency, order.card_amount_cents), ("eur", 500))
        self.assertEqual(order.stripe_session_id, "cs_shop_1")
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 5, "le stock ne bouge qu'au paiement")
        self.assertFalse(self.cart.cart_items.exists())

    @patch(SESSION_CREATE)
    def test_card_checkout_in_usd_charges_usd(self, mock_create):
        self._currency("USD")
        mock_create.return_value = Mock(id="cs_usd", url="https://checkout.stripe.com/pay/cs_usd")
        self._post_card()
        order = Order.objects.get(user=self.user)
        self.assertEqual((order.card_currency, order.card_amount_cents), ("usd", 575))

    def test_card_refused_when_prices_in_gnf(self):
        resp = self._post_card()
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "uniquement quand les prix sont affichés")
        self.assertFalse(Order.objects.exists())
        self.assertEqual(self.cart.cart_items.count(), 1)

    @patch(SESSION_CREATE, side_effect=stripe.APIConnectionError("réseau"))
    def test_stripe_error_creates_no_order_and_keeps_cart_and_points(self, _mock_create):
        self._currency("EUR")
        loyalty = LoyaltyAccount.objects.get(user=self.user)
        loyalty.points = 50
        loyalty.save()

        resp = self._post_card(use_points=20)

        self.assertEqual(resp.status_code, 200)
        self.assertFalse(Order.objects.exists())
        self.assertEqual(self.cart.cart_items.count(), 1)
        loyalty.refresh_from_db()
        self.assertEqual(loyalty.points, 50)

    def test_card_refused_under_stripe_minimum(self):
        self._currency("EUR")
        self.cart.cart_items.all().delete()
        cheap = Product.objects.create(name="Résistance", slug="resistance", category=self.product.category, price=1000, stock=10)
        CartItem.objects.create(cart=self.cart, product=cheap, quantity=1)  # 0,10 EUR
        resp = self._post_card()
        self.assertContains(resp, "Montant trop faible")
        self.assertFalse(Order.objects.exists())

    def test_insufficient_stock_blocks_any_checkout(self):
        self.cart.cart_items.update(quantity=10)
        resp = self.client.post("/shop/commander/", {"address": "Conakry", "phone": "+224600000000", "payment_method": "cash"})
        self.assertRedirects(resp, "/shop/panier/", fetch_redirect_response=False)
        self.assertFalse(Order.objects.exists())

    # --- Abandon : relancer ou annuler ---------------------------------------
    @patch(SESSION_EXPIRE)
    @patch(SESSION_RETRIEVE)
    @patch(SESSION_CREATE)
    def test_cancel_returns_items_to_cart_and_gives_points_back(self, mock_create, mock_retrieve, mock_expire):
        self._currency("EUR")
        loyalty = LoyaltyAccount.objects.get(user=self.user)
        loyalty.points = 50
        loyalty.save()
        mock_create.return_value = Mock(id="cs_cancel", url="https://checkout.stripe.com/pay/cs_cancel")
        self._post_card(use_points=20)
        loyalty.refresh_from_db()
        self.assertEqual(loyalty.points, 30, "points réservés dès la commande")
        order = Order.objects.get(user=self.user)

        mock_retrieve.return_value = Mock(id="cs_cancel", status="open")
        resp = self.client.post(f"/shop/commandes/{order.pk}/annuler/")

        self.assertRedirects(resp, "/shop/panier/", fetch_redirect_response=False)
        order.refresh_from_db()
        self.assertEqual((order.status, order.payment_status), ("cancelled", "failed"))
        loyalty.refresh_from_db()
        self.assertEqual(loyalty.points, 50)
        self.assertEqual(self.cart.cart_items.get().quantity, 2)
        mock_expire.assert_called_once_with("cs_cancel")

    @patch(SESSION_RETRIEVE)
    def test_cancel_refused_when_already_paid(self, mock_retrieve):
        order = Order.objects.create(user=self.user, payment_method="card", stripe_session_id="cs_paid")
        OrderItem.objects.create(order=order, product=self.product, quantity=1, unit_price=25000)
        mock_retrieve.return_value = Mock(id="cs_paid", status="complete")

        self.client.post(f"/shop/commandes/{order.pk}/annuler/")

        order.refresh_from_db()
        self.assertEqual(order.status, "pending")

    @patch(SESSION_EXPIRE)
    @patch(SESSION_RETRIEVE)
    @patch(SESSION_CREATE)
    def test_pay_again_replaces_session_and_expires_the_old_one(self, mock_create, mock_retrieve, mock_expire):
        order = Order.objects.create(user=self.user, payment_method="card", stripe_session_id="cs_old",
                                     card_currency="eur", card_amount_cents=250)
        OrderItem.objects.create(order=order, product=self.product, quantity=1, unit_price=25000)
        mock_retrieve.return_value = Mock(id="cs_old", status="open")
        mock_create.return_value = Mock(id="cs_new", url="https://checkout.stripe.com/pay/cs_new")

        resp = self.client.post(f"/shop/commandes/{order.pk}/payer-carte/")

        self.assertEqual(resp.url, "https://checkout.stripe.com/pay/cs_new")
        order.refresh_from_db()
        self.assertEqual(order.stripe_session_id, "cs_new")
        mock_expire.assert_called_once_with("cs_old")

    def test_order_page_shows_pay_and_cancel_buttons_while_unpaid(self):
        order = Order.objects.create(user=self.user, payment_method="card", card_currency="eur", card_amount_cents=250)
        resp = self.client.get(f"/shop/commandes/{order.pk}/?paiement=annule")
        self.assertContains(resp, "Paiement non effectué")
        self.assertContains(resp, f"/shop/commandes/{order.pk}/payer-carte/")
        self.assertContains(resp, f"/shop/commandes/{order.pk}/annuler/")
        self.assertContains(resp, "2,50 EUR")


@override_settings(**STRIPE_SETTINGS)
class ShopCardCheckoutMobileTest(TestCase):
    def setUp(self):
        _rates()
        self.user = User.objects.create_user(username="shop-card-mobile", password="pass")
        self.token, _ = Token.objects.get_or_create(user=self.user)
        self.api_client = APIClient()
        self.api_client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")
        category = Category.objects.create(name="Capteurs", slug="capteurs-card-mobile")
        self.product = Product.objects.create(
            name="Capteur Card Mobile", slug="capteur-card-mobile", category=category, price=25000, stock=5,
        )
        self.cart = Cart.objects.create(user=self.user)
        CartItem.objects.create(cart=self.cart, product=self.product, quantity=1)

    def _checkout(self, **extra):
        data = {"shipping_address": "Conakry", "phone": "+224600000000", "payment_method": "card"}
        data.update(extra)
        return self.api_client.post("/api/v1/orders/checkout/", data, format="json")

    @patch(SESSION_CREATE)
    def test_mobile_card_uses_display_currency_preference(self, mock_create):
        CurrencyPreference.objects.create(user=self.user, currency_code="EUR")
        mock_create.return_value = Mock(id="cs_mobile", url="https://checkout.stripe.com/pay/cs_mobile")

        resp = self._checkout()

        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.json()["url"], "https://checkout.stripe.com/pay/cs_mobile")
        self.assertEqual((resp.json()["currency"], resp.json()["amount"]), ("EUR", 2.5))
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 5)

    @patch(SESSION_CREATE)
    def test_mobile_card_with_explicit_usd(self, mock_create):
        mock_create.return_value = Mock(id="cs_mobile_usd", url="https://checkout.stripe.com/pay/cs_mobile_usd")
        resp = self._checkout(currency="USD")
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(Order.objects.get(user=self.user).card_currency, "usd")

    def test_mobile_card_refused_in_gnf(self):
        resp = self._checkout()
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["code"], "card_unavailable")
        self.assertIn("Orange Money", resp.json()["error"])
        self.assertFalse(Order.objects.exists())
        self.assertEqual(self.cart.cart_items.count(), 1)


@override_settings(**STRIPE_SETTINGS)
class ShopStripeWebhookTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="shop-webhook-user", password="pass", email="client@example.com")
        category = Category.objects.create(name="Capteurs", slug="capteurs-webhook")
        self.product = Product.objects.create(
            name="Capteur Webhook", slug="capteur-webhook", category=category, price=25000, stock=5,
        )
        self.order = Order.objects.create(
            user=self.user, shipping_address="Conakry", phone="+224600000000",
            contact_email="client@example.com", payment_method="card", payment_status="pending",
            stripe_session_id="cs_shop_evt_1", card_currency="eur", card_amount_cents=500,
        )
        OrderItem.objects.create(order=self.order, product=self.product, quantity=2, unit_price=self.product.price)

    def _send(self, event):
        with patch(CONSTRUCT_EVENT, return_value=event), self.captureOnCommitCallbacks(execute=True):
            return self.client.post(
                "/monetisation/stripe/webhook/", data="{}",
                content_type="application/json", HTTP_STRIPE_SIGNATURE="good-sig",
            )

    def test_paid_confirms_order_applies_stock_points_and_emails(self):
        resp = self._send(_shop_event("cs_shop_evt_1", 500))

        self.assertEqual(resp.status_code, 200)
        self.order.refresh_from_db()
        self.assertEqual((self.order.payment_status, self.order.status), ("paid", "confirmed"))
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 3)
        self.assertGreater(LoyaltyAccount.objects.get(user=self.user).points, 0)
        self.assertTrue(any("client@example.com" in m.to for m in mail.outbox))

    def test_paid_twice_applies_stock_only_once(self):
        self._send(_shop_event("cs_shop_evt_1", 500))
        self._send(_shop_event("cs_shop_evt_1", 500))
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 3)

    def test_amount_mismatch_does_not_confirm_order(self):
        self._send(_shop_event("cs_shop_evt_1", 100))
        self.order.refresh_from_db()
        self.assertEqual(self.order.payment_status, "failed")
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 5)

    def test_currency_mismatch_does_not_confirm_order(self):
        self._send(_shop_event("cs_shop_evt_1", 500, currency="usd"))
        self.order.refresh_from_db()
        self.assertEqual(self.order.payment_status, "failed")

    def test_expired_session_cancels_order_and_gives_points_back(self):
        loyalty = LoyaltyAccount.objects.get(user=self.user)
        self.order.pending_points_used = 20
        self.order.save()

        self._send(_shop_event("cs_shop_evt_1", 500, event_type="checkout.session.expired", payment_status="unpaid"))

        self.order.refresh_from_db()
        self.assertEqual((self.order.status, self.order.payment_status), ("cancelled", "failed"))
        loyalty.refresh_from_db()
        self.assertEqual(loyalty.points, 20)

    def test_expired_old_session_is_ignored(self):
        self._send(_shop_event("cs_replaced", 500, event_type="checkout.session.expired", payment_status="unpaid"))
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, "pending")

    def test_payment_on_cancelled_order_alerts_admin_without_touching_stock(self):
        self.order.status = "cancelled"
        self.order.payment_status = "failed"
        self.order.save()

        self._send(_shop_event("cs_shop_evt_1", 500))

        self.order.refresh_from_db()
        self.assertEqual(self.order.status, "cancelled")
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 5)
        self.assertTrue(any("annulée" in m.subject for m in mail.outbox))

    def test_stock_shortage_still_confirms_paid_order_and_alerts_admin(self):
        self.product.stock = 1
        self.product.save()

        self._send(_shop_event("cs_shop_evt_1", 500))

        self.order.refresh_from_db()
        self.assertEqual(self.order.payment_status, "paid")
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 0)
        self.assertTrue(any("Stock insuffisant" in m.subject for m in mail.outbox))


class LoyaltyDiscountTest(TestCase):
    def test_points_are_capped_to_what_the_cart_needs(self):
        from .views import loyalty_discount
        self.assertEqual(loyalty_discount(50000, 2000, 2000), (1250, 50000))
        self.assertEqual(loyalty_discount(50000, 25, 100), (20, 800))
        self.assertEqual(loyalty_discount(1000, 100, 100), (30, 1000))
        self.assertEqual(loyalty_discount(50000, "abc", 100), (0, 0))
        self.assertEqual(loyalty_discount(50000, 500, 40), (40, 1600))


@override_settings(**STRIPE_SETTINGS)
class LoyaltyPointsInOtherCurrenciesTest(TestCase):
    def setUp(self):
        _rates()
        self.user = User.objects.create_user(username="points-user", password="pass")
        self.client.force_login(self.user)
        category = Category.objects.create(name="Capteurs", slug="capteurs-points")
        product = Product.objects.create(name="Capteur Points", slug="capteur-points", category=category, price=25000, stock=5)
        cart = Cart.objects.create(user=self.user)
        CartItem.objects.create(cart=cart, product=product, quantity=2)  # 50 000 GNF
        loyalty = LoyaltyAccount.objects.get(user=self.user)
        loyalty.points = 1621
        loyalty.save()

    def test_points_script_is_valid_in_usd(self):
        session = self.client.session
        session["currency_code"] = "USD"
        session.save()
        resp = self.client.get("/shop/commander/")
        html = resp.content.decode()
        self.assertIn("const rate = 0.000115;", html)
        self.assertIn('max="1250"', html)  # 1 250 points couvrent les 50 000 GNF
        self.assertNotIn("0 pt = 0 GNF", html)

    @patch(SESSION_CREATE)
    def test_points_discount_applies_to_card_amount_in_usd(self, mock_create):
        session = self.client.session
        session["currency_code"] = "USD"
        session.save()
        mock_create.return_value = Mock(id="cs_pts", url="https://checkout.stripe.com/pay/cs_pts")
        self.client.post("/shop/commander/", {"address": "Conakry", "phone": "+224600000000",
                                              "payment_method": "card", "use_points": 500})
        order = Order.objects.get(user=self.user)
        self.assertEqual(order.discount, 20000)  # 500 points = 20 000 GNF
        self.assertEqual(order.card_amount_cents, 345)  # 30 000 GNF x 0.000115 = 3,45 USD
        self.assertEqual(LoyaltyAccount.objects.get(user=self.user).points, 1121)


@override_settings(**STRIPE_SETTINGS)
class ShopRefundAndDisputeTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="shop-refund", password="pass")
        self.order = Order.objects.create(
            user=self.user, payment_method="card", payment_status="paid", status="confirmed",
            stripe_session_id="cs_r", card_currency="eur", card_amount_cents=500, card_payment_id="pi_shop_1",
        )

    def _send(self, event_type, obj):
        event = stripe.Event.construct_from({"id": "evt", "object": "event", "type": event_type,
                                             "data": {"object": obj}}, "sk_test_dummy")
        with patch(CONSTRUCT_EVENT, return_value=event), self.captureOnCommitCallbacks(execute=True):
            return self.client.post("/monetisation/stripe/webhook/", data="{}",
                                    content_type="application/json", HTTP_STRIPE_SIGNATURE="sig")

    def test_full_refund_marks_order_refunded_and_alerts(self):
        self._send("charge.refunded", {"id": "ch", "object": "charge", "payment_intent": "pi_shop_1",
                                       "amount": 500, "amount_refunded": 500, "currency": "eur"})
        self.order.refresh_from_db()
        self.assertEqual(self.order.payment_status, "refunded")
        self.assertTrue(any("remboursée" in m.subject for m in mail.outbox))

    def test_dispute_then_won(self):
        dispute = {"id": "dp", "object": "dispute", "payment_intent": "pi_shop_1", "amount": 500,
                   "currency": "eur", "status": "needs_response"}
        self._send("charge.dispute.created", dispute)
        self.order.refresh_from_db()
        self.assertEqual(self.order.payment_status, "disputed")
        self._send("charge.dispute.closed", dict(dispute, status="won"))
        self.order.refresh_from_db()
        self.assertEqual(self.order.payment_status, "paid")
