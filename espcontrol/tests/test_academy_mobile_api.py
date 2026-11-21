from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from iot.book_catalog import BOOK_SLUG
from iot.models import AcademyBookLesson, AcademyPackAccess, AcademyPackPayment, Lecon, Organisation, Parcours


class AcademyMobileCatalogTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="academy-mobile-user", password="strongpass123")
        token, _ = Token.objects.get_or_create(user=self.user)
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

        org = Organisation.objects.create(nom="Academy mobile test", type="Université")
        self.parcours = Parcours.objects.create(
            organisation=org, created_by=self.user, titre="Livre 1",
            description="Test", niveau="Débutant", is_published=True,
        )
        self.free_lesson = Lecon.objects.create(parcours=self.parcours, titre="Les bases", ordre=1)
        self.paid_lesson = Lecon.objects.create(parcours=self.parcours, titre="Composants", ordre=2)
        AcademyBookLesson.objects.create(lecon=self.free_lesson, chapter_number="00", published=True)
        AcademyBookLesson.objects.create(lecon=self.paid_lesson, chapter_number="01", published=True)

    def test_free_chapter_unlocked_paid_chapter_locked(self):
        resp = self.client.get(reverse("mobile_academy_catalog"))
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        by_number = {c["number"]: c for c in data["chapters"]}
        self.assertTrue(by_number["00"]["unlocked"])
        self.assertEqual(by_number["00"]["lessons"][0]["lecon_id"], self.free_lesson.pk)
        self.assertFalse(by_number["01"]["unlocked"])
        self.assertEqual(by_number["01"]["lessons"][0]["lecon_id"], self.paid_lesson.pk)
        self.assertFalse(data["access_active"])

    def test_chapter_unlocked_with_active_pack_access(self):
        AcademyPackAccess.objects.create(
            user=self.user, pack_slug=BOOK_SLUG, provider="stripe",
            amount_eur=Decimal("9.99"), active=True,
        )
        resp = self.client.get(reverse("mobile_academy_catalog"))
        data = resp.json()
        by_number = {c["number"]: c for c in data["chapters"]}
        self.assertTrue(by_number["01"]["unlocked"])
        self.assertTrue(data["access_active"])

    def test_revoked_access_does_not_unlock(self):
        AcademyPackAccess.objects.create(
            user=self.user, pack_slug=BOOK_SLUG, provider="stripe",
            amount_eur=Decimal("9.99"), active=False,
        )
        resp = self.client.get(reverse("mobile_academy_catalog"))
        by_number = {c["number"]: c for c in resp.json()["chapters"]}
        self.assertFalse(by_number["01"]["unlocked"])

    def test_unpublished_lesson_not_counted_as_available(self):
        AcademyBookLesson.objects.filter(lecon=self.paid_lesson).update(published=False)
        resp = self.client.get(reverse("mobile_academy_catalog"))
        by_number = {c["number"]: c for c in resp.json()["chapters"]}
        self.assertFalse(by_number["01"]["available"])
        self.assertEqual(by_number["01"]["lessons_count"], 0)


class AcademyMobileCheckoutTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="academy-mobile-buyer", password="strongpass123")
        token, _ = Token.objects.get_or_create(user=self.user)
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

    def test_checkout_disabled_by_default(self):
        resp = self.client.post(reverse("mobile_academy_checkout"))
        self.assertEqual(resp.status_code, 503)

    @override_settings(STRIPE_ENABLED=True, STRIPE_SECRET_KEY="sk_test_fake", ACADEMY_BOOK_CHECKOUT_ENABLED=True)
    @patch("monetisation.academy_checkout.AcademyBookLesson.objects.filter")
    @patch("monetisation.academy_checkout.stripe.checkout.Session.create")
    def test_checkout_returns_url_and_session_id(self, create, lesson_filter):
        lesson_filter.return_value.exclude.return_value.exists.return_value = True
        create.return_value = SimpleNamespace(id="cs_test_mobile_academy", url="https://checkout.stripe.com/test-mobile")

        # L'appli doit envoyer l'accord (case CGV + renonciation au droit de rétractation).
        resp = self.client.post(reverse("mobile_academy_checkout"), {"accept_conditions": True}, format="json")

        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["url"], "https://checkout.stripe.com/test-mobile")
        self.assertEqual(data["session_id"], "cs_test_mobile_academy")
        self.assertEqual(create.call_args.kwargs["line_items"][0]["price_data"]["unit_amount"], 999)
        self.assertTrue(AcademyPackPayment.objects.filter(checkout_id="cs_test_mobile_academy").exists())

    @override_settings(STRIPE_ENABLED=True, STRIPE_SECRET_KEY="sk_test_fake", ACADEMY_BOOK_CHECKOUT_ENABLED=True)
    @patch("monetisation.academy_checkout.AcademyBookLesson.objects.filter")
    def test_checkout_rejects_user_who_already_owns_pack(self, lesson_filter):
        lesson_filter.return_value.exclude.return_value.exists.return_value = True
        AcademyPackAccess.objects.create(
            user=self.user, pack_slug=BOOK_SLUG, provider="stripe",
            amount_eur=Decimal("9.99"), active=True,
        )
        resp = self.client.post(reverse("mobile_academy_checkout"))
        self.assertEqual(resp.status_code, 409)
