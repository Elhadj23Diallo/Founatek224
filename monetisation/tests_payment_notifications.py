"""Le mail admin "Mobile Money a confirmer" ne doit partir que pour une
vraie demande Mobile Money en attente (MTN, Orange, Moov, Wave) — jamais
pour un règlement wallet (déjà soldé) ni pour Stripe/PayPal (confirmés
automatiquement par webhook, pas de confirmation manuelle admin)."""
from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase

from monetisation.models import PaymentRequest

User = get_user_model()


class PaymentRequestAdminNotificationTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="notif-user", password="pass")

    def test_pending_mobile_money_sends_admin_email(self):
        PaymentRequest.objects.create(
            user=self.user, provider="orange", phone_number="620000000",
            amount=3, status="pending",
        )
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Mobile Money", mail.outbox[0].body)
        self.assertIn("orange", mail.outbox[0].body)

    def test_successful_wallet_settlement_sends_no_email(self):
        PaymentRequest.objects.create(
            user=self.user, provider="wallet", amount=3, status="success",
        )
        self.assertEqual(len(mail.outbox), 0)

    def test_pending_stripe_sends_no_email(self):
        PaymentRequest.objects.create(
            user=self.user, provider="stripe", amount=3, status="pending",
            transaction_id="cs_test_notif",
        )
        self.assertEqual(len(mail.outbox), 0)

    def test_pending_paypal_sends_no_email(self):
        PaymentRequest.objects.create(
            user=self.user, provider="paypal", amount=3, status="pending",
            transaction_id="ORDER-notif",
        )
        self.assertEqual(len(mail.outbox), 0)
