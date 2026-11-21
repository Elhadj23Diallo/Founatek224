"""Case de renonciation, remboursements des contenus numériques et pages légales."""
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

from iot.book_catalog import BOOK_SLUG
from iot.models import (
    AcademyPackAccess, AcademyPackPayment, Organisation, Parcours, ParcoursAccess, ParcoursPayment,
)
from monetisation.consumer_law import WAIVER_ERROR
from monetisation.parcours_checkout import ParcoursCheckoutError, create_parcours_paypal_order
from monetisation.refunds import handle_paypal_event, handle_stripe_charge_refunded, handle_stripe_dispute

User = get_user_model()
STRIPE_ON = dict(STRIPE_ENABLED=True, STRIPE_SECRET_KEY="sk_test_fake", ACADEMY_BOOK_CHECKOUT_ENABLED=True)


def make_parcours(creator, prix="19.99"):
    org = Organisation.objects.create(nom="Org légal", type="Université")
    return Parcours.objects.create(
        organisation=org, created_by=creator, titre="Cours payant", description="...",
        niveau="Débutant", is_published=True, prix=Decimal(prix),
    )


@override_settings(**STRIPE_ON)
@patch("monetisation.academy_checkout.AcademyBookLesson.objects.filter")
@patch("monetisation.academy_checkout.stripe.checkout.Session.create")
class AcademyWaiverTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("waiver-buyer", password="pass-1234")
        self.client.force_login(self.user)

    def prepare(self, create, lesson_filter):
        lesson_filter.return_value.exclude.return_value.exists.return_value = True
        create.return_value = SimpleNamespace(id="cs_waiver", url="https://checkout.stripe.com/x")

    def test_checkout_refused_without_waiver(self, create, lesson_filter):
        self.prepare(create, lesson_filter)
        response = self.client.post(reverse("monetisation:academy_create_checkout"))
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], WAIVER_ERROR)
        create.assert_not_called()
        self.assertFalse(AcademyPackPayment.objects.exists())

    def test_waiver_is_recorded(self, create, lesson_filter):
        self.prepare(create, lesson_filter)
        response = self.client.post(reverse("monetisation:academy_create_checkout"), {"accept_conditions": "1"})
        self.assertEqual(response.status_code, 200)
        kwargs = create.call_args.kwargs
        self.assertEqual(kwargs["metadata"]["withdrawal_waiver"], "accepted")
        self.assertIn("rétractation", kwargs["custom_text"]["submit"]["message"])
        self.assertIsNotNone(AcademyPackPayment.objects.get(checkout_id="cs_waiver").waiver_accepted_at)


class ParcoursWaiverTests(TestCase):
    def setUp(self):
        self.creator = User.objects.create_user("waiver-creator", password="pass-1234")
        self.user = User.objects.create_user("waiver-student", password="pass-1234")
        self.parcours = make_parcours(self.creator)

    @override_settings(STRIPE_ENABLED=True, STRIPE_SECRET_KEY="sk_test_fake")
    @patch("monetisation.parcours_checkout.stripe.checkout.Session.create")
    def test_stripe_checkout_refused_without_waiver(self, create):
        self.client.force_login(self.user)
        response = self.client.post(reverse("monetisation:parcours_create_checkout", args=[self.parcours.id]))
        self.assertEqual(response.status_code, 400)
        create.assert_not_called()

    @override_settings(PAYPAL_CLIENT_ID="client-test")
    @patch("monetisation.parcours_checkout.requests.post")
    def test_paypal_order_refused_without_waiver(self, post):
        with self.assertRaises(ParcoursCheckoutError) as ctx:
            create_parcours_paypal_order(self.user, self.parcours)
        self.assertEqual(ctx.exception.status, 400)
        post.assert_not_called()

    @override_settings(PAYPAL_CLIENT_ID="client-test", PAYPAL_SECRET="secret-test")
    @patch("monetisation.parcours_checkout.requests.post")
    def test_paypal_order_records_waiver(self, post):
        post.return_value = SimpleNamespace(status_code=201, json=lambda: {"id": "ORDER-1"}, text="")
        create_parcours_paypal_order(self.user, self.parcours, waiver_accepted=True)
        self.assertIsNotNone(ParcoursPayment.objects.get(checkout_id="ORDER-1").waiver_accepted_at)


class ContentRefundTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("refund-buyer", password="pass-1234")
        self.payment = AcademyPackPayment.objects.create(
            user=self.user, pack_slug=BOOK_SLUG, provider="stripe", checkout_id="cs_paid",
            payment_reference="pi_paid", amount_eur=Decimal("9.99"), status="success",
        )
        self.access = AcademyPackAccess.objects.create(
            user=self.user, pack_slug=BOOK_SLUG, provider="stripe", payment_reference="pi_paid",
            amount_eur=Decimal("9.99"), active=True,
        )

    def charge(self, refunded=999):
        return {"payment_intent": "pi_paid", "amount_refunded": refunded, "amount": 999, "currency": "eur"}

    def test_full_refund_revokes_access_once(self):
        with self.captureOnCommitCallbacks(execute=True):
            handle_stripe_charge_refunded(self.charge())
        with self.captureOnCommitCallbacks(execute=True):
            handle_stripe_charge_refunded(self.charge())  # Stripe redélivre souvent
        self.access.refresh_from_db()
        self.payment.refresh_from_db()
        self.assertFalse(self.access.active)
        self.assertIsNotNone(self.access.revoked_at)
        self.assertEqual(self.payment.status, "refunded")
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Accès retiré", mail.outbox[0].subject)

    def test_partial_refund_keeps_access(self):
        with self.captureOnCommitCallbacks(execute=True):
            handle_stripe_charge_refunded(self.charge(refunded=300))
        self.access.refresh_from_db()
        self.assertTrue(self.access.active)
        self.assertIn("partiel", mail.outbox[0].subject)

    def test_dispute_suspends_then_restores_when_won(self):
        dispute = {"payment_intent": "pi_paid", "amount": 999, "currency": "eur", "status": "needs_response"}
        handle_stripe_dispute(dispute, closed=False)
        self.access.refresh_from_db()
        self.assertFalse(self.access.active)
        handle_stripe_dispute(dict(dispute, status="won"), closed=True)
        self.access.refresh_from_db()
        self.payment.refresh_from_db()
        self.assertTrue(self.access.active)
        self.assertEqual(self.payment.status, "success")

    def test_refund_of_old_payment_keeps_newer_purchase(self):
        AcademyPackAccess.objects.filter(pk=self.access.pk).update(payment_reference="pi_newer")
        handle_stripe_charge_refunded(self.charge())
        self.access.refresh_from_db()
        self.assertTrue(self.access.active)

    def test_paypal_refund_of_parcours_revokes_access(self):
        parcours = make_parcours(User.objects.create_user("refund-creator", password="pass-1234"))
        ParcoursPayment.objects.create(
            user=self.user, parcours=parcours, provider="paypal", checkout_id="ORDER-9",
            payment_reference="CAP-9", amount_eur=Decimal("19.99"), status="success",
        )
        access = ParcoursAccess.objects.create(
            user=self.user, parcours=parcours, provider="paypal", payment_reference="CAP-9",
            amount_eur=Decimal("19.99"), active=True,
        )
        handle_paypal_event({
            "event_type": "PAYMENT.CAPTURE.REFUNDED",
            "resource": {
                "id": "REFUND-1",
                "links": [{"rel": "up", "href": "https://api.paypal.com/v2/payments/captures/CAP-9"}],
                "seller_payable_breakdown": {"total_refunded_amount": {"value": "19.99"}},
            },
        })
        access.refresh_from_db()
        self.assertFalse(access.active)


class LegalPagesTests(TestCase):
    def test_pages_are_public(self):
        for name in ("legal_mentions", "legal_cgv", "legal_confidentialite"):
            response = self.client.get(reverse(name))
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, "PythonAnywhere LLP" if name != "legal_cgv" else "rétractation")

    def test_missing_fields_shown_only_to_superuser(self):
        self.assertNotContains(self.client.get(reverse("legal_mentions")), "LEGAL_SIRET")
        admin = User.objects.create_superuser("legal-admin", "admin@example.com", "pass-1234")
        self.client.force_login(admin)
        self.assertContains(self.client.get(reverse("legal_mentions")), "LEGAL_SIRET")

    @patch.dict("os.environ", {"LEGAL_SIRET": "123 456 789 00012"})
    def test_values_come_from_env(self):
        self.assertContains(self.client.get(reverse("legal_mentions")), "123 456 789 00012")

    def test_footer_links(self):
        self.assertContains(self.client.get(reverse("legal_cgv")), reverse("legal_confidentialite"))


class BackupCommandTests(TestCase):
    def test_backup_is_valid_and_rotated(self):
        import gzip
        import sqlite3
        import tempfile
        from io import StringIO
        from pathlib import Path
        from django.core.management import call_command

        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "site.sqlite3"
            con = sqlite3.connect(source)
            con.execute("create table t (x)")
            con.execute("insert into t values (42)")
            con.commit()
            con.close()
            dest = Path(tmp) / "backups"
            for i in range(3):
                (dest).mkdir(exist_ok=True)
                (dest / f"founatek-2026010{i}-000000.sqlite3.gz").write_bytes(b"old")
            out = StringIO()
            call_command("backup_db", source=str(source), dest=str(dest), keep=2, stdout=out)
            backups = sorted(dest.glob("founatek-*.sqlite3.gz"))
            self.assertEqual(len(backups), 2)
            restored = Path(tmp) / "restored.sqlite3"
            restored.write_bytes(gzip.decompress(backups[-1].read_bytes()))
            con = sqlite3.connect(restored)
            self.assertEqual(con.execute("select x from t").fetchone()[0], 42)
            con.close()
            self.assertIn("Sauvegarde OK", out.getvalue())


class ErrorReportFilterTests(TestCase):
    def test_sensitive_values_are_masked(self):
        from django.test import RequestFactory
        from monappli.reporting import SensitiveDataFilter
        request = RequestFactory().post("/x/", {"password1": "s3cret", "csrfmiddlewaretoken": "abc", "titre": "ok"},
                                        HTTP_AUTHORIZATION="Token abc123")
        request.COOKIES = {"csrftoken": "abc", "sessionid": "xyz"}
        f = SensitiveDataFilter()
        with self.settings(DEBUG=False):
            post = f.get_post_parameters(request)
            self.assertNotEqual(post["password1"], "s3cret")
            self.assertNotEqual(post["csrfmiddlewaretoken"], "abc")
            self.assertEqual(post["titre"], "ok")
            self.assertNotIn("abc123", str(f.get_safe_request_meta(request)))
            cookies = f.get_safe_cookies(request)
            self.assertNotEqual(cookies["csrftoken"], "abc")
            self.assertNotEqual(cookies["sessionid"], "xyz")


class MobileWaiverTests(TestCase):
    @override_settings(**STRIPE_ON)
    def test_mobile_checkout_requires_waiver(self):
        from rest_framework.authtoken.models import Token
        user = User.objects.create_user("mobile-buyer", password="pass-1234")
        token, _ = Token.objects.get_or_create(user=user)
        with patch("monetisation.academy_checkout.AcademyBookLesson.objects.filter") as lesson_filter:
            lesson_filter.return_value.exclude.return_value.exists.return_value = True
            response = self.client.post("/api/mobile/academy/checkout/", HTTP_AUTHORIZATION=f"Token {token.key}")
        self.assertEqual(response.status_code, 400)


class WaiverCheckboxDisplayTests(TestCase):
    @override_settings(**STRIPE_ON)
    def test_checkbox_on_parcours_checkout_page(self):
        creator = User.objects.create_user("display-creator", password="pass-1234")
        parcours = make_parcours(creator)
        self.client.force_login(User.objects.create_user("display-student", password="pass-1234"))
        response = self.client.get(reverse("monetisation:parcours_checkout_page", args=[parcours.id]))
        self.assertContains(response, 'name="accept_conditions"')
        self.assertContains(response, reverse("legal_cgv"))

    @override_settings(**STRIPE_ON)
    def test_checkbox_on_academy_page(self):
        self.client.force_login(User.objects.create_user("display-academy", password="pass-1234"))
        response = self.client.get("/academy/livre-1/")
        self.assertContains(response, 'name="accept_conditions"')
