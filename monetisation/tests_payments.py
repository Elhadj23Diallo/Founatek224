"""Tests de sécurité pour le système de paiement (PayPal, wallet, parrainage).

Chaque classe reproduit une faille trouvée dans monetisation/views.py (et son
équivalent mobile dans espcontrol/api_views.py) puis vérifie qu'elle est
corrigée. Aucun appel réseau réel vers PayPal : `requests.post` est mocké.
"""
import json
from unittest.mock import patch, Mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from monetisation.models import (
    Wallet, Subscription, PaymentRequest, Transaction,
    Referral, ReferralTransaction,
)

User = get_user_model()


class PayPalSubscriptionPriceTamperingTest(TestCase):
    """Faille 1 : un client qui envoie amount=0.01 pour plan=pro ne doit
    jamais pouvoir activer le plan Pro pour 1 centime."""

    def setUp(self):
        self.user = User.objects.create_user(username="paypal-user", password="pass")
        self.client.force_login(self.user)
        Subscription.objects.get_or_create(user=self.user, defaults={"plan": "free"})
        Wallet.objects.get_or_create(user=self.user, defaults={"balance": 0})

    @patch("requests.post")
    def test_create_order_ignores_client_amount_for_subscription(self, mock_post):
        mock_post.return_value = Mock(status_code=201, json=lambda: {"id": "ORDER-PRO-1"})

        resp = self.client.post(
            "/monetisation/paypal/create-order/",
            data=json.dumps({"type": "subscription", "plan": "pro", "amount": 0.01}),
            content_type="application/json",
        )

        self.assertEqual(resp.status_code, 200)
        sent_payload = mock_post.call_args.kwargs["json"]
        self.assertEqual(sent_payload["purchase_units"][0]["amount"]["value"], "15.00")
        payment = PaymentRequest.objects.get(transaction_id="ORDER-PRO-1")
        self.assertEqual(payment.amount, 15.0)

    def test_create_order_rejects_unknown_plan(self):
        resp = self.client.post(
            "/monetisation/paypal/create-order/",
            data=json.dumps({"type": "subscription", "plan": "ultra-vip"}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)

    def test_create_order_rejects_credit_amount_out_of_range(self):
        resp_low = self.client.post(
            "/monetisation/paypal/create-order/",
            data=json.dumps({"type": "credit", "amount": 0}),
            content_type="application/json",
        )
        self.assertEqual(resp_low.status_code, 400)

        resp_high = self.client.post(
            "/monetisation/paypal/create-order/",
            data=json.dumps({"type": "credit", "amount": 100000}),
            content_type="application/json",
        )
        self.assertEqual(resp_high.status_code, 400)

    @patch("requests.post")
    def test_capture_rejects_order_this_server_never_created(self, mock_post):
        """L'attaquant a obtenu un orderID 'COMPLETED' pour 0.01 EUR ailleurs
        (ou a juste inventé un orderID) et tente de le faire passer pour
        l'achat du plan pro. Comme ce n'est pas un PaymentRequest créé par
        create_paypal_order, il doit être rejeté avant même d'appeler PayPal."""
        mock_post.return_value = Mock(status_code=200, json=lambda: {
            "status": "COMPLETED",
            "purchase_units": [{
                "custom_id": f"subscription|pro|{self.user.id}",
                "payments": {"captures": [{"amount": {"currency_code": "EUR", "value": "0.01"}}]},
            }],
        })

        resp = self.client.post(
            "/monetisation/paypal/capture-order/",
            data=json.dumps({"orderID": "FORGED-ORDER"}),
            content_type="application/json",
        )

        self.assertEqual(resp.status_code, 400)
        sub = Subscription.objects.get(user=self.user)
        self.assertEqual(sub.plan, "free")
        self.assertEqual(ReferralTransaction.objects.count(), 0)

    @patch("requests.post")
    def test_full_flow_at_correct_price_activates_plan(self, mock_post):
        """Chemin heureux : create puis capture au vrai prix active bien le plan."""
        def fake_post(url, **kwargs):
            if "capture" in url:
                return Mock(status_code=200, json=lambda: {
                    "status": "COMPLETED",
                    "purchase_units": [{
                        "custom_id": f"subscription|pro|{self.user.id}",
                        "payments": {"captures": [{"amount": {"currency_code": "EUR", "value": "15.00"}}]},
                    }],
                })
            return Mock(status_code=201, json=lambda: {"id": "ORDER-PRO-OK"})

        mock_post.side_effect = fake_post

        create_resp = self.client.post(
            "/monetisation/paypal/create-order/",
            data=json.dumps({"type": "subscription", "plan": "pro"}),
            content_type="application/json",
        )
        self.assertEqual(create_resp.status_code, 200)

        capture_resp = self.client.post(
            "/monetisation/paypal/capture-order/",
            data=json.dumps({"orderID": "ORDER-PRO-OK"}),
            content_type="application/json",
        )
        self.assertEqual(capture_resp.status_code, 200)
        sub = Subscription.objects.get(user=self.user)
        self.assertEqual(sub.plan, "pro")

    @patch("requests.post")
    def test_capturing_twice_credits_only_once(self, mock_post):
        """Ne pas créditer deux fois la même commande PayPal (rejeu/double appel)."""
        def fake_post(url, **kwargs):
            if "capture" in url:
                return Mock(status_code=200, json=lambda: {
                    "status": "COMPLETED",
                    "purchase_units": [{
                        "custom_id": f"credit||{self.user.id}",
                        "payments": {"captures": [{"amount": {"currency_code": "EUR", "value": "10.00"}}]},
                    }],
                })
            return Mock(status_code=201, json=lambda: {"id": "ORDER-CREDIT-1"})

        mock_post.side_effect = fake_post

        self.client.post(
            "/monetisation/paypal/create-order/",
            data=json.dumps({"type": "credit", "amount": 10}),
            content_type="application/json",
        )
        self.client.post(
            "/monetisation/paypal/capture-order/",
            data=json.dumps({"orderID": "ORDER-CREDIT-1"}),
            content_type="application/json",
        )
        second_resp = self.client.post(
            "/monetisation/paypal/capture-order/",
            data=json.dumps({"orderID": "ORDER-CREDIT-1"}),
            content_type="application/json",
        )

        self.assertEqual(second_resp.status_code, 200)
        self.assertTrue(second_resp.json().get("already_processed"))
        wallet = Wallet.objects.get(user=self.user)
        self.assertEqual(wallet.balance, 10.0)
        self.assertEqual(Transaction.objects.filter(user=self.user, type="credit").count(), 1)


class MobilePayPalSubscriptionPriceTamperingTest(TestCase):
    """Même faille 1, côté API mobile (espcontrol/api_views.py)."""

    def setUp(self):
        self.user = User.objects.create_user(username="mobile-paypal-user", password="pass")
        self.token, _ = Token.objects.get_or_create(user=self.user)
        self.api_client = APIClient()
        self.api_client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")
        Subscription.objects.get_or_create(user=self.user, defaults={"plan": "free"})
        Wallet.objects.get_or_create(user=self.user, defaults={"balance": 0})

    @patch("requests.post")
    def test_create_order_ignores_client_amount_for_subscription(self, mock_post):
        mock_post.return_value = Mock(status_code=201, json=lambda: {"id": "MOBILE-ORDER-PRO-1"})

        resp = self.api_client.post(
            "/api/mobile/monetisation/paypal/create-order/",
            {"type": "subscription", "plan": "pro", "amount": 0.01},
            format="json",
        )

        self.assertEqual(resp.status_code, 201)
        sent_payload = mock_post.call_args.kwargs["json"]
        self.assertEqual(sent_payload["purchase_units"][0]["amount"]["value"], "15.00")
        payment = PaymentRequest.objects.get(transaction_id="MOBILE-ORDER-PRO-1")
        self.assertEqual(payment.amount, 15.0)

    @patch("requests.post")
    def test_capture_rejects_order_this_server_never_created(self, mock_post):
        mock_post.return_value = Mock(status_code=200, json=lambda: {
            "status": "COMPLETED",
            "purchase_units": [{
                "custom_id": f"subscription|pro|{self.user.id}",
                "payments": {"captures": [{"amount": {"currency_code": "EUR", "value": "0.01"}}]},
            }],
        })

        resp = self.api_client.post(
            "/api/mobile/monetisation/paypal/capture-order/",
            {"orderID": "MOBILE-FORGED-ORDER"},
            format="json",
        )

        self.assertEqual(resp.status_code, 400)
        sub = Subscription.objects.get(user=self.user)
        self.assertEqual(sub.plan, "free")


class MobileMoneyCallbackDisabledTest(TestCase):
    """Faille 2 : l'ancien /monetisation/wallet/callback/ n'était ni sous /api/
    (donc pas protégé par APIKeyMiddleware) ni signé : n'importe qui pouvait
    créditer un wallet et déclencher une commission sans payer. La route est
    désactivée (aucun opérateur ne l'appelait réellement)."""

    def setUp(self):
        self.referrer = User.objects.create_user(username="parrain-callback", password="pass")
        self.victim = User.objects.create_user(username="victime-callback", password="pass")
        Referral.objects.create(referrer=self.referrer, referred=self.victim, code="refcb123")
        self.wallet, _ = Wallet.objects.get_or_create(user=self.victim, defaults={"balance": 0})
        self.payment = PaymentRequest.objects.create(
            user=self.victim, provider="orange", phone_number="+224000000",
            amount=50, status="pending", transaction_id="TX-UNSIGNED-1",
        )

    def test_unsigned_callback_cannot_credit_wallet(self):
        resp = self.client.post(
            "/monetisation/wallet/callback/",
            data=json.dumps({"transaction_id": "TX-UNSIGNED-1", "status": "SUCCESS"}),
            content_type="application/json",
        )

        self.assertEqual(resp.status_code, 404)  # route supprimée
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.balance, 0)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, "pending")
        self.assertEqual(ReferralTransaction.objects.count(), 0)


class ReferralCommissionTimingTest(TestCase):
    """Faille 3 : la commission de parrainage ne doit être créée que lorsque
    le paiement est réellement confirmé, jamais à la simple création d'une
    demande 'pending'."""

    def setUp(self):
        self.referrer = User.objects.create_user(username="parrain-timing", password="pass")
        self.user = User.objects.create_user(username="filleul-timing", password="pass")
        Referral.objects.create(referrer=self.referrer, referred=self.user, code="reftiming1")
        self.client.force_login(self.user)

    def test_creating_a_pending_mobile_money_request_gives_no_commission(self):
        resp = self.client.post(
            "/monetisation/wallet/init/",
            {"provider": "orange", "phone_number": "+224000000", "amount": 100000},
        )
        self.assertEqual(PaymentRequest.objects.filter(user=self.user, status="pending").count(), 1)
        self.assertEqual(ReferralTransaction.objects.count(), 0)

    def test_admin_confirmation_gives_exactly_one_commission(self):
        pr = PaymentRequest.objects.create(
            user=self.user, provider="orange", phone_number="+224000000",
            amount=20.0, status="pending", transaction_id="TX-ADMIN-1",
        )
        staff = User.objects.create_user(username="staff-timing", password="pass", is_staff=True)
        token, _ = Token.objects.get_or_create(user=staff)
        api_client = APIClient()
        api_client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

        resp = api_client.post(
            f"/api/mobile/monetisation/admin/{pr.id}/review/",
            {"action": "confirm"}, format="json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(ReferralTransaction.objects.filter(referral__referred=self.user).count(), 1)

        # Reconfirmer la même demande ne doit pas redonner une 2e commission.
        resp2 = api_client.post(
            f"/api/mobile/monetisation/admin/{pr.id}/review/",
            {"action": "confirm"}, format="json",
        )
        self.assertEqual(resp2.status_code, 404)
        self.assertEqual(ReferralTransaction.objects.filter(referral__referred=self.user).count(), 1)
