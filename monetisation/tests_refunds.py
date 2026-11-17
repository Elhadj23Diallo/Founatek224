"""Tests : montants en Decimal, remboursements et litiges (Stripe, PayPal),
parcours « solde insuffisant » de la page Abonnement."""
import json
from decimal import Decimal
from unittest.mock import patch, Mock

import stripe
from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings

from monetisation.models import (
    PaymentRequest, Referral, ReferralTransaction, Subscription, Transaction, Wallet,
)
from monetisation.utils import round_money

User = get_user_model()
STRIPE_SETTINGS = dict(STRIPE_SECRET_KEY="sk_test_fake", STRIPE_WEBHOOK_SECRET="whsec_fake", STRIPE_ENABLED=True)
CONSTRUCT_EVENT = "monetisation.stripe_payments.stripe.Webhook.construct_event"


class RoundMoneyTest(TestCase):
    def test_exact_cents(self):
        self.assertEqual(round_money(0.1 + 0.2), Decimal("0.30"))
        self.assertEqual(round_money("1,005"), Decimal("1.01"))
        self.assertEqual(round_money(9900.709999999997), Decimal("9900.71"))

    def test_invalid_values_raise_value_error(self):
        for bad in (None, "abc", float("nan"), float("inf"), True):
            with self.assertRaises(ValueError):
                round_money(bad)


def _event(event_type, obj):
    return stripe.Event.construct_from(
        {"id": "evt_1", "object": "event", "type": event_type, "data": {"object": obj}},
        "sk_test_dummy",
    )


def _charge(refunded_cents, pi="pi_wallet_1", total_cents=1000):
    return {"id": "ch_1", "object": "charge", "payment_intent": pi, "amount": total_cents,
            "amount_refunded": refunded_cents, "currency": "eur"}


def _dispute(status="needs_response", pi="pi_wallet_1", amount_cents=1000):
    return {"id": "dp_1", "object": "dispute", "payment_intent": pi, "amount": amount_cents,
            "currency": "eur", "status": status}


@override_settings(**STRIPE_SETTINGS)
class StripeWalletRefundTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="client", password="p")
        parrain = User.objects.create_user(username="parrain", password="p")
        ref = Referral.objects.create(referrer=parrain, referred=self.user, code="r1")
        self.payment = PaymentRequest.objects.create(
            user=self.user, provider="stripe", amount=Decimal("10.00"), status="success",
            transaction_id="cs_1", external_id="pi_wallet_1", purpose="credit",
        )
        ReferralTransaction.objects.create(referral=ref, amount=500, description="c", payment=self.payment)
        Wallet.objects.filter(user=self.user).update(balance=Decimal("10.00"))

    def _send(self, event):
        with patch(CONSTRUCT_EVENT, return_value=event), self.captureOnCommitCallbacks(execute=True):
            return self.client.post("/monetisation/stripe/webhook/", data="{}",
                                    content_type="application/json", HTTP_STRIPE_SIGNATURE="sig")

    def _balance(self):
        return Wallet.objects.get(user=self.user).balance

    def test_full_refund_debits_wallet_cancels_commission_and_alerts(self):
        resp = self._send(_event("charge.refunded", _charge(1000)))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(self._balance(), Decimal("0.00"))
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, "refunded")
        self.assertFalse(ReferralTransaction.objects.exists())
        self.assertTrue(any("Remboursement Stripe" in m.subject for m in mail.outbox))

    def test_same_refund_twice_debits_once(self):
        self._send(_event("charge.refunded", _charge(1000)))
        self._send(_event("charge.refunded", _charge(1000)))
        self.assertEqual(self._balance(), Decimal("0.00"))
        self.assertEqual(Transaction.objects.filter(user=self.user, type="debit").count(), 1)

    def test_partial_then_full_refund(self):
        self._send(_event("charge.refunded", _charge(400)))
        self.assertEqual(self._balance(), Decimal("6.00"))
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, "success")
        self._send(_event("charge.refunded", _charge(1000)))
        self.assertEqual(self._balance(), Decimal("0.00"))

    def test_refund_after_spending_makes_balance_negative(self):
        Wallet.objects.filter(user=self.user).update(balance=Decimal("2.00"))
        self._send(_event("charge.refunded", _charge(1000)))
        self.assertEqual(self._balance(), Decimal("-8.00"))

    def test_dispute_blocks_then_won_gives_back(self):
        self._send(_event("charge.dispute.created", _dispute()))
        self.assertEqual(self._balance(), Decimal("0.00"))
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, "disputed")
        self._send(_event("charge.dispute.created", _dispute()))  # redélivré
        self.assertEqual(self._balance(), Decimal("0.00"))

        self._send(_event("charge.dispute.closed", _dispute(status="won")))
        self.assertEqual(self._balance(), Decimal("10.00"))
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, "success")
        self.assertTrue(ReferralTransaction.objects.exists())

    def test_dispute_lost_keeps_amount_withdrawn(self):
        self._send(_event("charge.dispute.created", _dispute()))
        self._send(_event("charge.dispute.closed", _dispute(status="lost")))
        self.assertEqual(self._balance(), Decimal("0.00"))
        self.payment.refresh_from_db()
        self.assertEqual((self.payment.status, self.payment.refunded_amount), ("refunded", Decimal("10.00")))
        self.assertFalse(ReferralTransaction.objects.exists())

    @patch("monetisation.refunds.stripe.checkout.Session.list")
    def test_old_payment_found_through_stripe_session(self, mock_list):
        PaymentRequest.objects.filter(pk=self.payment.pk).update(external_id="")
        mock_list.return_value = Mock(data=[Mock(id="cs_1")])
        self._send(_event("charge.refunded", _charge(1000, pi="pi_old")))
        self.assertEqual(self._balance(), Decimal("0.00"))
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.external_id, "pi_old")

    @patch("monetisation.refunds.stripe.checkout.Session.list")
    def test_unknown_payment_alerts_admin(self, mock_list):
        mock_list.return_value = Mock(data=[])
        self._send(_event("charge.refunded", _charge(1000, pi="pi_unknown")))
        self.assertEqual(self._balance(), Decimal("10.00"))
        self.assertTrue(any("à vérifier" in m.subject for m in mail.outbox))

    def test_redelivered_completed_event_does_not_recredit_a_refunded_payment(self):
        self._send(_event("charge.refunded", _charge(1000)))
        completed = _event("checkout.session.completed", {
            "id": "cs_1", "object": "checkout.session", "payment_status": "paid",
            "amount_total": 1000, "currency": "eur", "payment_intent": "pi_wallet_1",
            "metadata": {"kind": "wallet_topup"},
        })
        self._send(completed)
        self.assertEqual(self._balance(), Decimal("0.00"))


@override_settings(**STRIPE_SETTINGS)
class StripeTopupStoresPaymentIntentTest(TestCase):
    def test_completed_topup_records_payment_intent_and_links_commission(self):
        user = User.objects.create_user(username="c2", password="p")
        parrain = User.objects.create_user(username="p2", password="p")
        Referral.objects.create(referrer=parrain, referred=user, code="r2")
        PaymentRequest.objects.create(user=user, provider="stripe", amount=10, status="pending", transaction_id="cs_2")
        event = _event("checkout.session.completed", {
            "id": "cs_2", "object": "checkout.session", "payment_status": "paid",
            "amount_total": 1000, "currency": "eur", "payment_intent": "pi_2",
            "metadata": {"kind": "wallet_topup"},
        })
        with patch(CONSTRUCT_EVENT, return_value=event):
            self.client.post("/monetisation/stripe/webhook/", data="{}", content_type="application/json",
                             HTTP_STRIPE_SIGNATURE="sig")
        payment = PaymentRequest.objects.get(transaction_id="cs_2")
        self.assertEqual((payment.external_id, payment.purpose, payment.status), ("pi_2", "credit", "success"))
        self.assertEqual(ReferralTransaction.objects.get().payment, payment)
        self.assertEqual(Wallet.objects.get(user=user).balance, Decimal("10.00"))


@override_settings(PAYPAL_WEBHOOK_ID="WH-TEST")
class PayPalWebhookTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="pp", password="p")
        Wallet.objects.filter(user=self.user).update(balance=Decimal("20.00"))
        self.credit = PaymentRequest.objects.create(
            user=self.user, provider="paypal", amount=Decimal("20.00"), status="success",
            transaction_id="ORDER-1", external_id="CAP-CREDIT", purpose="credit",
        )
        Subscription.objects.filter(user=self.user).update(plan="basic")
        self.sub_payment = PaymentRequest.objects.create(
            user=self.user, provider="paypal", amount=Decimal("3.00"), status="success",
            transaction_id="ORDER-2", external_id="CAP-SUB", purpose="subscription",
        )

    def _post(self, event, verified=True):
        with patch("monetisation.refunds._verify_paypal_webhook", return_value=verified), \
                self.captureOnCommitCallbacks(execute=True):
            return self.client.post("/monetisation/paypal/webhook/", data=json.dumps(event),
                                    content_type="application/json")

    @staticmethod
    def _refund(capture_id, total):
        return {"event_type": "PAYMENT.CAPTURE.REFUNDED", "resource": {
            "id": "REF-1", "amount": {"value": total, "currency_code": "EUR"},
            "seller_payable_breakdown": {"total_refunded_amount": {"value": total, "currency_code": "EUR"}},
            "links": [{"rel": "up", "href": f"https://api.paypal.com/v2/payments/captures/{capture_id}"}],
        }}

    def test_not_configured_or_bad_signature_is_refused(self):
        with self.settings(PAYPAL_WEBHOOK_ID=""):
            self.assertEqual(self._post(self._refund("CAP-CREDIT", "20.00")).status_code, 503)
        self.assertEqual(self._post(self._refund("CAP-CREDIT", "20.00"), verified=False).status_code, 400)
        self.assertEqual(Wallet.objects.get(user=self.user).balance, Decimal("20.00"))

    def test_credit_refund_debits_wallet_once(self):
        self._post(self._refund("CAP-CREDIT", "20.00"))
        self._post(self._refund("CAP-CREDIT", "20.00"))
        self.assertEqual(Wallet.objects.get(user=self.user).balance, Decimal("0.00"))

    def test_subscription_refund_goes_back_to_free_plan(self):
        self._post(self._refund("CAP-SUB", "3.00"))
        self.assertEqual(Subscription.objects.get(user=self.user).plan, "free")
        self.assertEqual(Wallet.objects.get(user=self.user).balance, Decimal("20.00"))

    def test_dispute_created_then_resolved_for_seller(self):
        created = {"event_type": "CUSTOMER.DISPUTE.CREATED", "resource": {
            "dispute_id": "PP-D-1", "dispute_amount": {"value": "20.00", "currency_code": "EUR"},
            "disputed_transactions": [{"seller_transaction_id": "CAP-CREDIT"}],
        }}
        self._post(created)
        self.assertEqual(Wallet.objects.get(user=self.user).balance, Decimal("0.00"))
        resolved = {"event_type": "CUSTOMER.DISPUTE.RESOLVED", "resource": {
            "dispute_id": "PP-D-1", "dispute_outcome": {"outcome_code": "RESOLVED_SELLER_FAVOUR"},
            "disputed_transactions": [{"seller_transaction_id": "CAP-CREDIT"}],
        }}
        self._post(resolved)
        self.assertEqual(Wallet.objects.get(user=self.user).balance, Decimal("20.00"))

    @patch("requests.post")
    def test_signature_is_checked_with_paypal(self, mock_post):
        mock_post.return_value = Mock(status_code=200, json=lambda: {"verification_status": "SUCCESS"})
        headers = {
            "HTTP_PAYPAL_AUTH_ALGO": "SHA256withRSA", "HTTP_PAYPAL_CERT_URL": "https://api.paypal.com/cert",
            "HTTP_PAYPAL_TRANSMISSION_ID": "t1", "HTTP_PAYPAL_TRANSMISSION_SIG": "sig",
            "HTTP_PAYPAL_TRANSMISSION_TIME": "2026-11-17T18:00:00Z",
        }
        raw = json.dumps(self._refund("CAP-CREDIT", "5.00"))
        resp = self.client.post("/monetisation/paypal/webhook/", data=raw, content_type="application/json", **headers)
        self.assertEqual(resp.status_code, 200)
        sent = json.loads(mock_post.call_args.kwargs["data"])
        self.assertEqual(sent["webhook_id"], "WH-TEST")
        self.assertEqual(sent["webhook_event"]["resource"]["id"], "REF-1")
        self.assertEqual(Wallet.objects.get(user=self.user).balance, Decimal("15.00"))


class PayPalCaptureStoresCaptureIdTest(TestCase):
    @patch("requests.post")
    def test_capture_id_and_purpose_are_recorded(self, mock_post):
        user = User.objects.create_user(username="cap", password="p")
        self.client.force_login(user)

        def fake_post(url, **kwargs):
            if "capture" in url:
                return Mock(status_code=200, json=lambda: {
                    "status": "COMPLETED",
                    "purchase_units": [{"custom_id": f"credit||{user.id}", "payments": {"captures": [
                        {"id": "CAP-XYZ", "amount": {"currency_code": "EUR", "value": "10.00"}}]}}],
                })
            return Mock(status_code=201, json=lambda: {"id": "ORDER-X"})

        mock_post.side_effect = fake_post
        self.client.post("/monetisation/paypal/create-order/", data=json.dumps({"type": "credit", "amount": 10}),
                         content_type="application/json")
        self.client.post("/monetisation/paypal/capture-order/", data=json.dumps({"orderID": "ORDER-X"}),
                         content_type="application/json")
        payment = PaymentRequest.objects.get(transaction_id="ORDER-X")
        self.assertEqual((payment.external_id, payment.purpose), ("CAP-XYZ", "credit"))
        self.assertEqual(Wallet.objects.get(user=user).balance, Decimal("10.00"))


@override_settings(**STRIPE_SETTINGS)
class InsufficientBalanceFlowTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="abo", password="p")
        self.client.force_login(self.user)
        Wallet.objects.filter(user=self.user).update(balance=Decimal("3.00"))

    def test_page_always_offers_wallet_and_explains_missing_amount(self):
        Wallet.objects.filter(user=self.user).update(balance=Decimal("0.00"))
        resp = self.client.get("/monetisation/abonnement/")
        self.assertContains(resp, '<option value="wallet">')
        self.assertContains(resp, 'id="wallet-insufficient"')
        self.assertContains(resp, "const WALLET_BALANCE = 0.00;")

    def test_wallet_payment_with_insufficient_balance_says_how_much_is_missing(self):
        resp = self.client.post("/monetisation/abonnement/", {"plan": "pro", "provider": "wallet"})
        self.assertContains(resp, "il vous manque 12.00 €")
        self.assertEqual(Subscription.objects.get(user=self.user).plan, "free")

    def test_wallet_payment_with_enough_balance(self):
        resp = self.client.post("/monetisation/abonnement/", {"plan": "basic", "provider": "wallet"})
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(Wallet.objects.get(user=self.user).balance, Decimal("0.00"))
        self.assertEqual(Subscription.objects.get(user=self.user).plan, "basic")

    def test_topup_page_prefilled_from_subscription(self):
        resp = self.client.get("/monetisation/acheter-credit/?montant=12&retour=abonnement")
        self.assertContains(resp, 'value="12.00"')
        self.assertContains(resp, "vous reviendrez sur la page Abonnement")
        self.assertContains(resp, 'const RETURN_TO = "abonnement";')

    @patch("monetisation.stripe_payments.create_wallet_topup_checkout")
    def test_stripe_topup_from_subscription_comes_back_to_it(self, mock_create):
        mock_create.return_value = Mock(url="https://checkout.stripe.com/x")
        self.client.post("/monetisation/stripe/create-checkout/",
                         data=json.dumps({"amount": 12, "return_to": "abonnement"}), content_type="application/json")
        success_url, cancel_url = mock_create.call_args.args[2], mock_create.call_args.args[3]
        self.assertIn("retour=abonnement", success_url)
        self.assertTrue(cancel_url.endswith("/monetisation/abonnement/"))

    def test_success_page_waits_then_returns_to_subscription(self):
        PaymentRequest.objects.create(user=self.user, provider="stripe", amount=12, status="pending", transaction_id="cs_9")
        resp = self.client.get("/monetisation/stripe/success/?session_id=cs_9&retour=abonnement")
        self.assertContains(resp, "se met à jour toute seule")
        PaymentRequest.objects.filter(transaction_id="cs_9").update(status="success")
        resp = self.client.get("/monetisation/stripe/success/?session_id=cs_9&retour=abonnement")
        self.assertContains(resp, "Wallet crédité")
        self.assertContains(resp, 'window.location.href = "/monetisation/abonnement/"')
