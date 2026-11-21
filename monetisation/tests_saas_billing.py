"""Abonnements par carte avec renouvellement automatique (Stripe)."""
from datetime import datetime, timedelta
from datetime import timezone as dt_timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

import stripe
from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from monetisation.models import PaymentRequest, Subscription, Transaction, Wallet
from monetisation.refunds import apply_refund
from monetisation.saas_billing import (
    SAAS_KIND, handle_checkout_completed, handle_invoice_paid, handle_invoice_payment_failed,
    handle_subscription_deleted, handle_subscription_updated,
)
from monetisation.utils import sync_subscription_expiry

User = get_user_model()
ON = dict(STRIPE_ENABLED=True, STRIPE_AUTO_RENEW_ENABLED=True, STRIPE_SECRET_KEY="sk_test_fake",
          STRIPE_WEBHOOK_SECRET="whsec_fake")
LOCMEM = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "saas-tests"}}
CREATE = "monetisation.saas_billing.stripe.checkout.Session.create"


def ts(day):
    return int(datetime.combine(day, datetime.min.time(), tzinfo=dt_timezone.utc).timestamp()) + 12 * 3600


def invoice(sub_id="sub_1", user_id=None, plan="basic", amount=300, invoice_id="in_1", end_day=None, new_api=False):
    end_day = end_day or (timezone.localdate() + timedelta(days=30))
    metadata = {"kind": SAAS_KIND, "plan": plan, "user_id": str(user_id)}
    data = {
        "id": invoice_id, "customer": "cus_1", "currency": "eur", "amount_paid": amount,
        "attempt_count": 1,
        "lines": {"data": [{"period": {"start": ts(timezone.localdate()), "end": ts(end_day)}}]},
    }
    if new_api:
        data["parent"] = {"subscription_details": {"subscription": sub_id, "metadata": metadata}}
        data["payments"] = {"data": [{"payment": {"payment_intent": "pi_new"}}]}
    else:
        data.update({"subscription": sub_id, "subscription_details": {"metadata": metadata}, "payment_intent": "pi_1"})
    return data


class CheckoutTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("saas-buyer", email="buyer@example.com", password="pass-1234")
        self.client.force_login(self.user)
        self.url = reverse("monetisation:saas_create_checkout")

    def test_disabled_by_default(self):
        self.assertEqual(self.client.post(self.url, {"plan": "basic", "accept_conditions": "1"}).status_code, 503)

    @override_settings(**ON)
    @patch(CREATE)
    def test_requires_consent(self, create):
        response = self.client.post(self.url, {"plan": "basic"})
        self.assertEqual(response.status_code, 400)
        create.assert_not_called()

    @override_settings(**ON)
    @patch(CREATE)
    def test_creates_monthly_subscription(self, create):
        create.return_value = SimpleNamespace(id="cs_sub", url="https://checkout.stripe.com/s")
        response = self.client.post(self.url, {"plan": "pro", "accept_conditions": "1"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["url"], "https://checkout.stripe.com/s")
        kwargs = create.call_args.kwargs
        self.assertEqual(kwargs["mode"], "subscription")
        price = kwargs["line_items"][0]["price_data"]
        self.assertEqual((price["unit_amount"], price["recurring"]["interval"]), (1500, "month"))
        self.assertEqual(kwargs["subscription_data"]["metadata"]["kind"], SAAS_KIND)
        self.assertNotIn("trial_end", kwargs["subscription_data"])
        self.assertEqual(kwargs["customer_email"], "buyer@example.com")
        self.assertIsNotNone(Subscription.objects.get(user=self.user).auto_renew_consent_at)

    @override_settings(**ON)
    @patch(CREATE)
    def test_paid_days_become_trial_and_plan_change_is_refused(self, create):
        create.return_value = SimpleNamespace(id="cs_sub", url="https://checkout.stripe.com/s")
        end = timezone.localdate() + timedelta(days=10)
        Subscription.objects.filter(user=self.user).update(plan="basic", end_date=end)
        self.assertEqual(self.client.post(self.url, {"plan": "pro", "accept_conditions": "1"}).status_code, 409)
        self.assertEqual(self.client.post(self.url, {"plan": "basic", "accept_conditions": "1"}).status_code, 200)
        trial_end = create.call_args.kwargs["subscription_data"]["trial_end"]
        first_charge = timezone.localtime(datetime.fromtimestamp(trial_end, tz=dt_timezone.utc))
        self.assertEqual(first_charge.date(), end + timedelta(days=1))

    @override_settings(**ON)
    @patch(CREATE)
    def test_refused_when_already_automatic(self, create):
        Subscription.objects.filter(user=self.user).update(billing="stripe_auto", stripe_subscription_id="sub_x",
                                                           plan="basic", end_date=timezone.localdate())
        self.assertEqual(self.client.post(self.url, {"plan": "basic", "accept_conditions": "1"}).status_code, 409)


@override_settings(CACHES=LOCMEM, **ON)
class WebhookTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("saas-hook", email="hook@example.com", password="pass-1234")
        self.sub = Subscription.objects.get(user=self.user)

    def test_checkout_completed_links_stripe_ids(self):
        handle_checkout_completed({
            "id": "cs_1", "mode": "subscription", "status": "complete", "customer": "cus_1",
            "subscription": "sub_1", "client_reference_id": str(self.user.pk),
            "metadata": {"kind": SAAS_KIND, "plan": "basic", "user_id": str(self.user.pk)},
        })
        self.sub.refresh_from_db()
        self.assertEqual((self.sub.billing, self.sub.stripe_customer_id, self.sub.stripe_subscription_id),
                         ("stripe_auto", "cus_1", "sub_1"))

    def test_invoice_paid_extends_once(self):
        end = timezone.localdate() + timedelta(days=30)
        with self.captureOnCommitCallbacks(execute=True):
            handle_invoice_paid(invoice(user_id=self.user.pk, end_day=end))
        with self.captureOnCommitCallbacks(execute=True):
            handle_invoice_paid(invoice(user_id=self.user.pk, end_day=end))  # redélivrance
        self.sub.refresh_from_db()
        self.assertEqual((self.sub.plan, self.sub.end_date, self.sub.billing), ("basic", end, "stripe_auto"))
        payment = PaymentRequest.objects.get(transaction_id="in_1")
        self.assertEqual((payment.purpose, payment.external_id, payment.amount), ("subscription", "pi_1", Decimal("3.00")))
        self.assertEqual(Transaction.objects.filter(user=self.user, type="subscription").count(), 1)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("activé", mail.outbox[0].subject)

    def test_new_api_shape(self):
        handle_invoice_paid(invoice(user_id=self.user.pk, plan="pro", amount=1500, new_api=True))
        self.sub.refresh_from_db()
        self.assertEqual(self.sub.plan, "pro")
        self.assertEqual(PaymentRequest.objects.get(transaction_id="in_1").external_id, "pi_new")

    def test_wrong_amount_does_not_extend(self):
        handle_invoice_paid(invoice(user_id=self.user.pk, plan="pro", amount=300))
        self.sub.refresh_from_db()
        self.assertEqual(self.sub.plan, "free")
        self.assertFalse(PaymentRequest.objects.filter(transaction_id="in_1").exists())

    def test_trial_invoice_keeps_paid_days(self):
        end = timezone.localdate() + timedelta(days=5)
        Subscription.objects.filter(pk=self.sub.pk).update(plan="basic", end_date=end)
        handle_invoice_paid(invoice(user_id=self.user.pk, amount=0))
        self.sub.refresh_from_db()
        self.assertEqual((self.sub.end_date, self.sub.billing, self.sub.stripe_subscription_id), (end, "stripe_auto", "sub_1"))

    def test_payment_failed_emails_once_per_attempt(self):
        Subscription.objects.filter(pk=self.sub.pk).update(billing="stripe_auto", stripe_subscription_id="sub_1", plan="basic")
        handle_invoice_payment_failed(invoice(user_id=self.user.pk))
        handle_invoice_payment_failed(invoice(user_id=self.user.pk))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("échoué", mail.outbox[0].subject)

    def test_cancellation_synced_then_deleted(self):
        end = timezone.localdate() + timedelta(days=12)
        Subscription.objects.filter(pk=self.sub.pk).update(billing="stripe_auto", stripe_subscription_id="sub_1",
                                                           plan="basic", end_date=end)
        handle_subscription_updated({"id": "sub_1", "status": "active", "cancel_at_period_end": True, "metadata": {}})
        self.sub.refresh_from_db()
        self.assertTrue(self.sub.cancel_at_period_end)
        handle_subscription_deleted({"id": "sub_1", "status": "canceled", "metadata": {}})
        self.sub.refresh_from_db()
        self.assertEqual((self.sub.billing, self.sub.stripe_subscription_id, self.sub.plan), ("manual", "", "basic"))
        self.assertTrue(self.sub.cancel_at_period_end)

    @patch("monetisation.stripe_payments.stripe.Webhook.construct_event")
    def test_webhook_routes_invoice_events(self, construct):
        construct.return_value = stripe.Event.construct_from({
            "id": "evt_1", "object": "event", "type": "invoice.paid",
            "data": {"object": dict(invoice(user_id=self.user.pk), object="invoice")},
        }, "sk_test_fake")
        response = self.client.post(reverse("monetisation:stripe_webhook"), data=b"{}",
                                    content_type="application/json", HTTP_STRIPE_SIGNATURE="sig")
        self.assertEqual(response.status_code, 200)
        self.sub.refresh_from_db()
        self.assertEqual(self.sub.plan, "basic")


@override_settings(**ON)
class SiteActionsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("saas-site", password="pass-1234")
        self.client.force_login(self.user)
        Wallet.objects.get_or_create(user=self.user, defaults={"balance": 100})
        Wallet.objects.filter(user=self.user).update(balance=100)
        Subscription.objects.filter(user=self.user).update(
            billing="stripe_auto", stripe_subscription_id="sub_9", stripe_customer_id="cus_9",
            plan="basic", end_date=timezone.localdate() + timedelta(days=20),
        )
        self.url = reverse("monetisation:monetisation_abonnement")

    @patch("monetisation.saas_billing.stripe.Subscription.modify")
    def test_cancel_and_reactivate_update_stripe(self, modify):
        self.client.post(self.url, {"action": "cancel_at_period_end"})
        modify.assert_called_with("sub_9", cancel_at_period_end=True)
        self.assertTrue(Subscription.objects.get(user=self.user).cancel_at_period_end)
        self.client.post(self.url, {"action": "reactivate"})
        modify.assert_called_with("sub_9", cancel_at_period_end=False)
        self.assertFalse(Subscription.objects.get(user=self.user).cancel_at_period_end)

    @patch("monetisation.saas_billing.stripe.Subscription.modify", side_effect=stripe.APIConnectionError("réseau"))
    def test_cancel_failure_changes_nothing(self, modify):
        response = self.client.post(self.url, {"action": "cancel_at_period_end"})
        self.assertContains(response, "Stripe")
        self.assertFalse(Subscription.objects.get(user=self.user).cancel_at_period_end)

    def test_wallet_payment_blocked_while_automatic(self):
        response = self.client.post(self.url, {"plan": "pro", "provider": "wallet"})
        self.assertContains(response, "prélevé automatiquement")
        self.assertEqual(Wallet.objects.get(user=self.user).balance, 100)
        self.assertEqual(Subscription.objects.get(user=self.user).plan, "basic")

    def test_page_shows_card_management(self):
        response = self.client.get(self.url)
        self.assertContains(response, "Gérer ma carte")
        self.assertContains(response, "prélèvement automatique par carte")

    @patch("monetisation.saas_billing.stripe.billing_portal.Session.create")
    def test_billing_portal_redirects_to_stripe(self, create):
        create.return_value = SimpleNamespace(url="https://billing.stripe.com/p/1")
        response = self.client.post(reverse("monetisation:saas_billing_portal"))
        self.assertRedirects(response, "https://billing.stripe.com/p/1", fetch_redirect_response=False)
        self.assertEqual(create.call_args.kwargs["customer"], "cus_9")

    @patch("monetisation.saas_billing.stripe.Subscription.cancel")
    def test_refund_stops_future_charges(self, cancel):
        payment = PaymentRequest.objects.create(user=self.user, provider="stripe", phone_number="", amount=Decimal("3"),
                                                status="success", transaction_id="in_9", external_id="pi_9",
                                                purpose="subscription")
        with self.captureOnCommitCallbacks(execute=True):
            apply_refund(payment.pk, Decimal("3"), "Stripe")
        cancel.assert_called_once_with("sub_9")
        sub = Subscription.objects.get(user=self.user)
        self.assertEqual((sub.plan, sub.billing, sub.stripe_subscription_id), ("free", "manual", ""))

    def test_grace_period_for_failed_renewal(self):
        sub = Subscription.objects.get(user=self.user)
        sub.end_date = timezone.localdate() - timedelta(days=2)
        self.assertEqual(sync_subscription_expiry(sub).plan, "basic")
        sub.end_date = timezone.localdate() - timedelta(days=4)
        self.assertEqual(sync_subscription_expiry(sub).plan, "free")


class PageOptionTests(TestCase):
    def setUp(self):
        self.client.force_login(User.objects.create_user("saas-page", password="pass-1234"))

    def test_option_hidden_when_disabled(self):
        self.assertNotContains(self.client.get(reverse("monetisation:monetisation_abonnement")), 'value="card_auto"')

    @override_settings(**ON)
    def test_option_and_consent_shown_when_enabled(self):
        response = self.client.get(reverse("monetisation:monetisation_abonnement"))
        self.assertContains(response, 'value="card_auto"')
        self.assertContains(response, 'id="auto-renew-consent"')
