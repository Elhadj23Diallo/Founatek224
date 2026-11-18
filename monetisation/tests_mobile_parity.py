"""API mobile alignée sur le site : abonnement (solde insuffisant détaillé),
statut d'une recharge Stripe, règles du parrainage, moyens de recharge,
relance / annulation d'une commande carte de la boutique."""
from decimal import Decimal
from unittest.mock import patch, Mock

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from founatekapp.models import Category, Product, Order, OrderItem, Cart, LoyaltyAccount
from monetisation.models import PaymentRequest, Subscription, Wallet

User = get_user_model()
STRIPE_SETTINGS = dict(STRIPE_SECRET_KEY="sk_test_fake", STRIPE_WEBHOOK_SECRET="whsec_fake", STRIPE_ENABLED=True)


@override_settings(**STRIPE_SETTINGS)
class MobileParityTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="mob", password="p")
        token, _ = Token.objects.get_or_create(user=self.user)
        self.api = APIClient()
        self.api.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        Wallet.objects.filter(user=self.user).update(balance=Decimal("3.00"))

    def test_upgrade_with_insufficient_balance_explains_what_is_missing(self):
        resp = self.api.post("/api/mobile/monetisation/upgrade/", {"plan": "pro"}, format="json")
        self.assertEqual(resp.status_code, 402)
        body = resp.json()
        self.assertEqual((body["code"], body["missing"], body["price"]), ("insufficient_balance", 12.0, 15))
        self.assertEqual(Subscription.objects.get(user=self.user).plan, "free")

    def test_upgrade_with_enough_balance(self):
        resp = self.api.post("/api/mobile/monetisation/upgrade/", {"plan": "basic"}, format="json")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual((resp.json()["plan"], resp.json()["balance"]), ("basic", 0.0))

    @patch("monetisation.stripe_payments.create_wallet_topup_checkout")
    def test_stripe_topup_returns_session_id_then_status(self, mock_create):
        mock_create.return_value = Mock(url="https://checkout.stripe.com/x", id="cs_mob")
        resp = self.api.post("/api/mobile/monetisation/stripe/create-checkout/", {"amount": 10}, format="json")
        self.assertEqual(resp.json()["session_id"], "cs_mob")
        PaymentRequest.objects.create(user=self.user, provider="stripe", amount=10, status="pending", transaction_id="cs_mob")
        status = self.api.get("/api/mobile/monetisation/stripe/status/?session_id=cs_mob").json()
        self.assertEqual((status["status"], status["credited"]), ("pending", False))
        self.assertEqual(self.api.get("/api/mobile/monetisation/stripe/status/?session_id=other").status_code, 404)

    def test_dashboard_lists_available_topup_methods(self):
        topup = self.api.get("/api/mobile/monetisation/").json()["topup"]
        self.assertEqual((topup["card"]["enabled"], topup["card"]["min"]), (True, 10))
        self.assertFalse(topup["mobile_money"]["enabled"])

    def test_referral_exposes_conversion_rules(self):
        body = self.api.get("/api/mobile/monetisation/referral/").json()
        self.assertEqual((body["points_per_euro"], body["min_points_to_convert"], body["can_convert"]), (1000, 1000, False))

    @patch("founatekapp.stripe_checkout.stripe.checkout.Session.expire")
    @patch("founatekapp.stripe_checkout.stripe.checkout.Session.retrieve")
    @patch("founatekapp.stripe_checkout.stripe.checkout.Session.create")
    def test_shop_order_pay_again_and_cancel(self, mock_create, mock_retrieve, mock_expire):
        from founatekapp.models import ExchangeRate
        ExchangeRate.objects.create(currency_code="EUR", currency_symbol="€", rate_from_gnf="0.000100")
        cat = Category.objects.create(name="C", slug="c-mob")
        prod = Product.objects.create(name="P", slug="p-mob", category=cat, price=25000, stock=5)
        order = Order.objects.create(user=self.user, payment_method="card", stripe_session_id="cs_old",
                                     card_currency="eur", card_amount_cents=250)
        OrderItem.objects.create(order=order, product=prod, quantity=1, unit_price=25000)

        detail = self.api.get(f"/api/v1/orders/{order.pk}/").json()
        self.assertEqual((detail["awaiting_card_payment"], detail["card_amount"], detail["card_currency"]), (True, 2.5, "EUR"))

        mock_retrieve.return_value = Mock(id="cs_old", status="open")
        mock_create.return_value = Mock(id="cs_new", url="https://checkout.stripe.com/new")
        resp = self.api.post(f"/api/v1/orders/{order.pk}/pay-card/")
        self.assertEqual(resp.json()["url"], "https://checkout.stripe.com/new")

        mock_retrieve.return_value = Mock(id="cs_new", status="open")
        resp = self.api.post(f"/api/v1/orders/{order.pk}/cancel/")
        self.assertEqual(resp.json()["cancelled"], True)
        self.assertEqual(Cart.objects.get(user=self.user).cart_items.count(), 1)
        self.assertEqual(self.api.post(f"/api/v1/orders/{order.pk}/pay-card/").status_code, 400)
