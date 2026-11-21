from decimal import Decimal
from unittest.mock import patch, Mock
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from iot.models import Organisation, Parcours, ParcoursAccess, ParcoursPayment
from monetisation.parcours_checkout import (
    handle_parcours_stripe_event, capture_parcours_paypal_order, ParcoursCheckoutError,
)

User = get_user_model()


def _make_parcours(creator, prix="19.99", is_published=True):
    organisation = Organisation.objects.create(nom="Org checkout", type="Université")
    return Parcours.objects.create(
        organisation=organisation, created_by=creator, titre="Cours payant",
        description="...", niveau="Débutant", is_published=is_published, prix=Decimal(prix),
    )


class ParcoursStripeWebhookTests(TestCase):
    def setUp(self):
        self.creator = User.objects.create_user("parcours-stripe-creator", password="testpass")
        self.user = User.objects.create_user("parcours-stripe-buyer", password="testpass")
        self.parcours = _make_parcours(self.creator)
        self.payment = ParcoursPayment.objects.create(
            user=self.user, parcours=self.parcours, provider="stripe",
            checkout_id="cs_test_parcours_1", amount_eur=Decimal("19.99"),
        )

    def session(self, **changes):
        data = {
            "id": self.payment.checkout_id,
            "mode": "payment",
            "payment_status": "paid",
            "currency": "eur",
            "amount_total": 1999,
            "payment_intent": "pi_test_parcours",
            "client_reference_id": str(self.user.pk),
            "metadata": {
                "kind": "parcours_access",
                "parcours_id": str(self.parcours.pk),
                "user_id": str(self.user.pk),
            },
        }
        data.update(changes)
        return data

    def test_unpaid_does_not_grant_access(self):
        handle_parcours_stripe_event("checkout.session.completed", self.session(payment_status="unpaid"))
        self.assertFalse(ParcoursAccess.objects.filter(user=self.user).exists())

    def test_wrong_amount_does_not_grant_access(self):
        handle_parcours_stripe_event("checkout.session.completed", self.session(amount_total=100))
        self.assertFalse(ParcoursAccess.objects.filter(user=self.user).exists())

    def test_wrong_user_does_not_grant_access(self):
        handle_parcours_stripe_event("checkout.session.completed", self.session(client_reference_id="999999"))
        self.assertFalse(ParcoursAccess.objects.filter(user=self.user).exists())

    def test_wrong_parcours_metadata_does_not_grant_access(self):
        handle_parcours_stripe_event(
            "checkout.session.completed",
            self.session(metadata={"kind": "parcours_access", "parcours_id": "999999", "user_id": str(self.user.pk)}),
        )
        self.assertFalse(ParcoursAccess.objects.filter(user=self.user).exists())

    def test_paid_grants_access_once(self):
        handle_parcours_stripe_event("checkout.session.completed", self.session())
        handle_parcours_stripe_event("checkout.session.completed", self.session())
        self.assertEqual(
            ParcoursAccess.objects.filter(user=self.user, parcours=self.parcours, active=True).count(), 1
        )
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, "success")

    def test_expired_session_never_grants_access(self):
        handle_parcours_stripe_event("checkout.session.expired", self.session())
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, "failed")
        self.assertFalse(ParcoursAccess.objects.filter(user=self.user).exists())

    @override_settings(STRIPE_ENABLED=True, STRIPE_SECRET_KEY="sk_test_fake")
    @patch("monetisation.parcours_checkout.stripe.checkout.Session.create")
    def test_checkout_uses_parcours_price(self, create):
        create.return_value = SimpleNamespace(id="cs_test_new", url="https://checkout.stripe.com/test")
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("monetisation:parcours_create_checkout", args=[self.parcours.id]), {"accept_conditions": "1"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(create.call_args.kwargs["line_items"][0]["price_data"]["unit_amount"], 1999)
        self.assertTrue(ParcoursPayment.objects.filter(checkout_id="cs_test_new", status="pending").exists())

    def test_checkout_rejects_free_parcours(self):
        free = _make_parcours(self.creator, prix="0")
        self.client.force_login(self.user)
        response = self.client.post(reverse("monetisation:parcours_create_checkout", args=[free.id]))
        self.assertEqual(response.status_code, 400)

    def test_checkout_rejects_already_owned(self):
        ParcoursAccess.objects.create(user=self.user, parcours=self.parcours, provider="stripe", active=True)
        self.client.force_login(self.user)
        for enabled in (True, False):
            with self.subTest(stripe_enabled=enabled), override_settings(STRIPE_ENABLED=enabled):
                response = self.client.post(reverse("monetisation:parcours_create_checkout", args=[self.parcours.id]))
                self.assertEqual(response.status_code, 409)

    @override_settings(STRIPE_ENABLED=False)
    def test_checkout_unavailable_when_stripe_off(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse("monetisation:parcours_create_checkout", args=[self.parcours.id]))
        self.assertEqual(response.status_code, 503)

    def test_paypal_order_rejects_already_owned_even_if_paypal_off(self):
        from monetisation.parcours_checkout import create_parcours_paypal_order
        ParcoursAccess.objects.create(user=self.user, parcours=self.parcours, provider="paypal", active=True)
        with override_settings(PAYPAL_CLIENT_ID=""):
            with self.assertRaises(ParcoursCheckoutError) as ctx:
                create_parcours_paypal_order(self.user, self.parcours)
        self.assertEqual(ctx.exception.status, 409)

    def test_anonymous_checkout_requires_login(self):
        response = self.client.post(reverse("monetisation:parcours_create_checkout", args=[self.parcours.id]))
        self.assertEqual(response.status_code, 302)


class ParcoursPayPalCaptureTests(TestCase):
    def setUp(self):
        self.creator = User.objects.create_user("parcours-pp-creator", password="testpass")
        self.user = User.objects.create_user("parcours-pp-buyer", password="testpass")
        self.parcours = _make_parcours(self.creator)
        self.payment = ParcoursPayment.objects.create(
            user=self.user, parcours=self.parcours, provider="paypal",
            checkout_id="ORDER-1", amount_eur=Decimal("19.99"),
        )

    def _capture_result(self, **changes):
        data = {
            "status": "COMPLETED",
            "purchase_units": [{
                "custom_id": f"parcours|{self.parcours.id}|{self.user.id}",
                "payments": {"captures": [{"id": "CAP-1", "amount": {"currency_code": "EUR", "value": "19.99"}}]},
            }],
        }
        data.update(changes)
        return data

    @patch("monetisation.parcours_checkout.requests.post")
    def test_successful_capture_grants_access(self, mock_post):
        mock_post.return_value = Mock(json=lambda: self._capture_result())
        capture_parcours_paypal_order(self.user, "ORDER-1")
        self.assertTrue(
            ParcoursAccess.objects.filter(user=self.user, parcours=self.parcours, active=True).exists()
        )
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, "success")

    @patch("monetisation.parcours_checkout.requests.post")
    def test_wrong_custom_id_does_not_grant_access(self, mock_post):
        mock_post.return_value = Mock(json=lambda: self._capture_result(
            purchase_units=[{
                "custom_id": "parcours|999999|999999",
                "payments": {"captures": [{"id": "CAP-1", "amount": {"currency_code": "EUR", "value": "19.99"}}]},
            }]
        ))
        with self.assertRaises(ParcoursCheckoutError):
            capture_parcours_paypal_order(self.user, "ORDER-1")
        self.assertFalse(ParcoursAccess.objects.filter(user=self.user).exists())

    @patch("monetisation.parcours_checkout.requests.post")
    def test_insufficient_amount_does_not_grant_access(self, mock_post):
        mock_post.return_value = Mock(json=lambda: self._capture_result(
            purchase_units=[{
                "custom_id": f"parcours|{self.parcours.id}|{self.user.id}",
                "payments": {"captures": [{"id": "CAP-1", "amount": {"currency_code": "EUR", "value": "1.00"}}]},
            }]
        ))
        with self.assertRaises(ParcoursCheckoutError):
            capture_parcours_paypal_order(self.user, "ORDER-1")
        self.assertFalse(ParcoursAccess.objects.filter(user=self.user).exists())

    def test_other_users_order_cannot_be_captured(self):
        other = User.objects.create_user("parcours-pp-other", password="testpass")
        with self.assertRaises(ParcoursCheckoutError):
            capture_parcours_paypal_order(other, "ORDER-1")
        self.assertFalse(ParcoursAccess.objects.filter(parcours=self.parcours).exists())

    @patch("monetisation.parcours_checkout.requests.post")
    def test_capture_is_idempotent(self, mock_post):
        mock_post.return_value = Mock(json=lambda: self._capture_result())
        capture_parcours_paypal_order(self.user, "ORDER-1")
        capture_parcours_paypal_order(self.user, "ORDER-1")
        self.assertEqual(
            ParcoursAccess.objects.filter(user=self.user, parcours=self.parcours).count(), 1
        )
