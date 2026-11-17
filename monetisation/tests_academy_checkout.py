from decimal import Decimal
from unittest.mock import patch
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from iot.book_catalog import BOOK_SLUG
from iot.models import AcademyPackAccess, AcademyPackPayment
from monetisation.academy_checkout import handle_academy_stripe_event


class AcademyCheckoutTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("academy_checkout_test", password="testpass")
        self.payment = AcademyPackPayment.objects.create(
            user=self.user, pack_slug=BOOK_SLUG, provider="stripe",
            checkout_id="cs_test_academy_1", amount_eur=Decimal("9.99"),
        )

    def session(self, **changes):
        data = {
            "id": self.payment.checkout_id,
            "mode": "payment",
            "payment_status": "paid",
            "currency": "eur",
            "amount_total": 999,
            "payment_intent": "pi_test_academy",
            "client_reference_id": str(self.user.pk),
            "metadata": {
                "kind": "academy_book_pack",
                "pack_slug": BOOK_SLUG,
                "user_id": str(self.user.pk),
            },
        }
        data.update(changes)
        return data

    def test_unpaid_does_not_grant_access(self):
        handle_academy_stripe_event("checkout.session.completed", self.session(payment_status="unpaid"))
        self.assertFalse(AcademyPackAccess.objects.filter(user=self.user).exists())

    def test_wrong_amount_does_not_grant_access(self):
        handle_academy_stripe_event("checkout.session.completed", self.session(amount_total=1000))
        self.assertFalse(AcademyPackAccess.objects.filter(user=self.user).exists())

    def test_wrong_user_does_not_grant_access(self):
        handle_academy_stripe_event("checkout.session.completed", self.session(client_reference_id="999999"))
        self.assertFalse(AcademyPackAccess.objects.filter(user=self.user).exists())

    def test_paid_grants_access_once(self):
        handle_academy_stripe_event("checkout.session.completed", self.session())
        handle_academy_stripe_event("checkout.session.completed", self.session())
        self.assertEqual(AcademyPackAccess.objects.filter(user=self.user, active=True).count(), 1)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, "success")

    def test_expired_session_never_grants_access(self):
        handle_academy_stripe_event("checkout.session.expired", self.session())
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, "failed")
        self.assertFalse(AcademyPackAccess.objects.filter(user=self.user).exists())

    @override_settings(STRIPE_ENABLED=True, STRIPE_SECRET_KEY="sk_test_fake", ACADEMY_BOOK_CHECKOUT_ENABLED=True)
    @patch("monetisation.academy_checkout.AcademyBookLesson.objects.filter")
    @patch("monetisation.academy_checkout.stripe.checkout.Session.create")
    def test_checkout_uses_fixed_price(self, lesson_filter, create):
        lesson_filter.return_value.exclude.return_value.exists.return_value = True
        create.return_value = SimpleNamespace(id="cs_test_new", url="https://checkout.stripe.com/test")
        self.client.force_login(self.user)
        response = self.client.post(reverse("monetisation:academy_create_checkout"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(create.call_args.kwargs["line_items"][0]["price_data"]["unit_amount"], 999)
        self.assertTrue(AcademyPackPayment.objects.filter(checkout_id="cs_test_new", status="pending").exists())

    def test_checkout_disabled_by_default(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse("monetisation:academy_create_checkout"))
        self.assertEqual(response.status_code, 503)

    def test_anonymous_checkout_requires_login(self):
        response = self.client.post(reverse("monetisation:academy_create_checkout"))
        self.assertEqual(response.status_code, 302)
