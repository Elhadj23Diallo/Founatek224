"""Tests pour la recharge du wallet par carte (Stripe Checkout + webhook).

Aucune vraie requête réseau vers Stripe : stripe.checkout.Session.create et
stripe.Webhook.construct_event sont mockés.
"""
import json
from unittest.mock import patch, Mock

import stripe
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from monetisation.models import Wallet, PaymentRequest, Transaction, Referral, ReferralTransaction

User = get_user_model()


@override_settings(STRIPE_SECRET_KEY="sk_test_fake", STRIPE_WEBHOOK_SECRET="whsec_fake", STRIPE_ENABLED=True)
class StripeCreateCheckoutTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="stripe-user", password="pass")
        self.client.force_login(self.user)

    @patch("monetisation.stripe_payments.stripe.checkout.Session.create")
    def test_creates_pending_payment_request_and_returns_url(self, mock_create):
        mock_create.return_value = Mock(id="cs_test_1", url="https://checkout.stripe.com/pay/cs_test_1")

        resp = self.client.post(
            "/monetisation/stripe/create-checkout/",
            data=json.dumps({"amount": 10}),
            content_type="application/json",
        )

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["url"], "https://checkout.stripe.com/pay/cs_test_1")
        payment = PaymentRequest.objects.get(transaction_id="cs_test_1")
        self.assertEqual(payment.provider, "stripe")
        self.assertEqual(payment.amount, 10.0)
        self.assertEqual(payment.status, "pending")

        sent_kwargs = mock_create.call_args.kwargs
        self.assertEqual(sent_kwargs["line_items"][0]["price_data"]["unit_amount"], 1000)
        self.assertEqual(sent_kwargs["metadata"]["user_id"], str(self.user.id))

    def test_amount_below_minimum_is_rejected_before_calling_stripe(self):
        resp = self.client.post(
            "/monetisation/stripe/create-checkout/",
            data=json.dumps({"amount": 3}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(PaymentRequest.objects.count(), 0)

    def test_amount_above_maximum_is_rejected(self):
        resp = self.client.post(
            "/monetisation/stripe/create-checkout/",
            data=json.dumps({"amount": 5000}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(PaymentRequest.objects.count(), 0)


@override_settings(STRIPE_SECRET_KEY="", STRIPE_WEBHOOK_SECRET="", STRIPE_ENABLED=False)
class StripeDisabledTest(TestCase):
    def test_create_checkout_unavailable_when_keys_missing(self):
        user = User.objects.create_user(username="stripe-off-user", password="pass")
        self.client.force_login(user)

        resp = self.client.post(
            "/monetisation/stripe/create-checkout/",
            data=json.dumps({"amount": 10}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 503)


@override_settings(STRIPE_SECRET_KEY="sk_test_fake", STRIPE_WEBHOOK_SECRET="whsec_fake", STRIPE_ENABLED=True)
class StripeWebhookTest(TestCase):
    def setUp(self):
        self.referrer = User.objects.create_user(username="parrain-stripe", password="pass")
        self.user = User.objects.create_user(username="stripe-webhook-user", password="pass")
        Referral.objects.create(referrer=self.referrer, referred=self.user, code="refstripe1")
        self.wallet, _ = Wallet.objects.get_or_create(user=self.user, defaults={"balance": 0})
        self.payment = PaymentRequest.objects.create(
            user=self.user, provider="stripe", amount=10.0,
            status="pending", transaction_id="cs_test_valid",
        )

    def _completed_event(self, session_id="cs_test_valid", amount_total=1000, currency="eur", payment_status="paid"):
        return {
            "type": "checkout.session.completed",
            "data": {"object": {
                "id": session_id,
                "payment_status": payment_status,
                "amount_total": amount_total,
                "currency": currency,
            }},
        }

    @patch("monetisation.stripe_payments.stripe.Webhook.construct_event")
    def test_invalid_signature_returns_400_and_does_not_credit(self, mock_construct):
        mock_construct.side_effect = stripe.SignatureVerificationError("Signature invalide", "bad-sig")

        resp = self.client.post(
            "/monetisation/stripe/webhook/",
            data="{}", content_type="application/json",
            HTTP_STRIPE_SIGNATURE="bad-sig",
        )

        self.assertEqual(resp.status_code, 400)
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.balance, 0)
        self.assertEqual(ReferralTransaction.objects.count(), 0)

    @patch("monetisation.stripe_payments.stripe.Webhook.construct_event")
    def test_valid_payment_credits_wallet_once(self, mock_construct):
        mock_construct.return_value = self._completed_event()

        resp = self.client.post(
            "/monetisation/stripe/webhook/",
            data="{}", content_type="application/json",
            HTTP_STRIPE_SIGNATURE="good-sig",
        )

        self.assertEqual(resp.status_code, 200)
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.balance, 10.0)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, "success")
        self.assertEqual(Transaction.objects.filter(user=self.user, type="credit").count(), 1)
        self.assertEqual(ReferralTransaction.objects.filter(referral__referred=self.user).count(), 1)

    @patch("monetisation.stripe_payments.stripe.Webhook.construct_event")
    def test_same_event_delivered_twice_credits_only_once(self, mock_construct):
        mock_construct.return_value = self._completed_event()

        self.client.post(
            "/monetisation/stripe/webhook/", data="{}",
            content_type="application/json", HTTP_STRIPE_SIGNATURE="good-sig",
        )
        resp2 = self.client.post(
            "/monetisation/stripe/webhook/", data="{}",
            content_type="application/json", HTTP_STRIPE_SIGNATURE="good-sig",
        )

        self.assertEqual(resp2.status_code, 200)
        self.assertTrue(resp2.json().get("already_processed"))
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.balance, 10.0)
        self.assertEqual(Transaction.objects.filter(user=self.user, type="credit").count(), 1)
        self.assertEqual(ReferralTransaction.objects.filter(referral__referred=self.user).count(), 1)

    @patch("monetisation.stripe_payments.stripe.Webhook.construct_event")
    def test_amount_mismatch_does_not_credit(self, mock_construct):
        # Stripe dit avoir encaissé 5 EUR alors que le PaymentRequest attend 10 EUR.
        mock_construct.return_value = self._completed_event(amount_total=500)

        resp = self.client.post(
            "/monetisation/stripe/webhook/",
            data="{}", content_type="application/json",
            HTTP_STRIPE_SIGNATURE="good-sig",
        )

        self.assertEqual(resp.status_code, 200)  # on répond vite, mais sans créditer
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.balance, 0)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, "failed")
        self.assertEqual(ReferralTransaction.objects.count(), 0)
