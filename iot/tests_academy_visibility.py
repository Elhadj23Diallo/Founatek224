from decimal import Decimal
from django.contrib.auth import get_user_model
from django.test import TestCase

from .academy_access import can_read_lesson, filter_readable_lessons
from .book_catalog import BOOK_SLUG
from .models import AcademyBookLesson, AcademyPackAccess, Lecon, Organisation, Parcours


class AcademyLessonVisibilityTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("academy_visibility", password="testpass")
        self.organisation = Organisation.objects.create(nom="Academy test", type="Université")
        self.parcours = Parcours.objects.create(
            organisation=self.organisation, created_by=self.user, titre="Livre test",
            description="Tests de visibilité", niveau="Débutant", is_published=True
        )
        self.free = Lecon.objects.create(parcours=self.parcours, titre="Gratuit", ordre=1)
        self.paid = Lecon.objects.create(parcours=self.parcours, titre="Payant", ordre=2)
        self.draft = Lecon.objects.create(parcours=self.parcours, titre="Brouillon", ordre=3)
        self.other = Lecon.objects.create(parcours=self.parcours, titre="Hors livre", ordre=4)
        AcademyBookLesson.objects.create(lecon=self.free, chapter_number="00", published=True)
        AcademyBookLesson.objects.create(lecon=self.paid, chapter_number="01", published=True)
        AcademyBookLesson.objects.create(lecon=self.draft, chapter_number="02", published=False)

    def test_free_visible_paid_hidden(self):
        ids = set(filter_readable_lessons(Lecon.objects.all(), self.user).values_list("pk", flat=True))
        self.assertEqual(ids, {self.free.pk, self.other.pk})
        self.assertTrue(can_read_lesson(self.user, self.free))
        self.assertFalse(can_read_lesson(self.user, self.paid))

    def test_buyer_sees_paid_but_not_draft(self):
        AcademyPackAccess.objects.create(
            user=self.user, pack_slug=BOOK_SLUG, provider="stripe",
            amount_eur=Decimal("9.99"), active=True
        )
        ids = set(filter_readable_lessons(Lecon.objects.all(), self.user).values_list("pk", flat=True))
        self.assertEqual(ids, {self.free.pk, self.paid.pk, self.other.pk})

    def test_nested_parcours_api_hides_paid_content(self):
        self.client.force_login(self.user)
        response = self.client.get("/iot/api/parcours/%s/" % self.parcours.pk)
        self.assertEqual(response.status_code, 200)
        titles = {item["titre"] for item in response.json()["lecons"]}
        self.assertEqual(titles, {"Gratuit", "Hors livre"})

    def test_paid_lesson_api_denies_without_purchase(self):
        self.client.force_login(self.user)
        response = self.client.get("/iot/api/lecons/%s/" % self.paid.pk)
        self.assertIn(response.status_code, (403, 404))
