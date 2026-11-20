from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from .academy_access import can_read_lesson, filter_readable_lessons
from .models import Lecon, Organisation, Parcours, ParcoursAccess, Project, Quiz

User = get_user_model()


class ParcoursAccessTests(TestCase):
    """can_read_parcours / can_read_lesson / filter_readable_lessons pour un
    Parcours payant ordinaire (hors Academy Livre 1)."""

    def setUp(self):
        self.creator = User.objects.create_user("parcours-creator", password="testpass")
        self.buyer = User.objects.create_user("parcours-buyer", password="testpass")
        self.stranger = User.objects.create_user("parcours-stranger", password="testpass")
        self.staff = User.objects.create_user("parcours-staff", password="testpass", is_staff=True)
        organisation = Organisation.objects.create(nom="Org test", type="Université")
        self.free_parcours = Parcours.objects.create(
            organisation=organisation, created_by=self.creator, titre="Gratuit",
            description="...", niveau="Débutant", is_published=True, prix=0,
        )
        self.paid_parcours = Parcours.objects.create(
            organisation=organisation, created_by=self.creator, titre="Payant",
            description="...", niveau="Débutant", is_published=True, prix=Decimal("19.99"),
        )
        self.free_lesson = Lecon.objects.create(parcours=self.free_parcours, titre="L1", ordre=1)
        self.paid_lesson = Lecon.objects.create(parcours=self.paid_parcours, titre="L1", ordre=1)

    def test_free_parcours_readable_by_anyone(self):
        self.assertTrue(can_read_lesson(self.stranger, self.free_lesson))
        self.assertTrue(can_read_lesson(None, self.free_lesson))

    def test_paid_parcours_blocked_for_stranger(self):
        self.assertFalse(can_read_lesson(self.stranger, self.paid_lesson))
        self.assertFalse(can_read_lesson(None, self.paid_lesson))

    def test_paid_parcours_readable_by_creator_and_staff(self):
        self.assertTrue(can_read_lesson(self.creator, self.paid_lesson))
        self.assertTrue(can_read_lesson(self.staff, self.paid_lesson))

    def test_paid_parcours_readable_after_active_access(self):
        ParcoursAccess.objects.create(
            user=self.buyer, parcours=self.paid_parcours, provider="stripe", active=True,
        )
        self.assertTrue(can_read_lesson(self.buyer, self.paid_lesson))

    def test_revoked_access_blocks_again(self):
        from django.utils import timezone
        ParcoursAccess.objects.create(
            user=self.buyer, parcours=self.paid_parcours, provider="stripe",
            active=True, revoked_at=timezone.now(),
        )
        self.assertFalse(can_read_lesson(self.buyer, self.paid_lesson))

    def test_filter_readable_lessons_hides_paid_for_stranger(self):
        ids = set(filter_readable_lessons(Lecon.objects.all(), self.stranger).values_list("pk", flat=True))
        self.assertIn(self.free_lesson.pk, ids)
        self.assertNotIn(self.paid_lesson.pk, ids)

    def test_filter_readable_lessons_shows_paid_for_buyer(self):
        ParcoursAccess.objects.create(
            user=self.buyer, parcours=self.paid_parcours, provider="stripe", active=True,
        )
        ids = set(filter_readable_lessons(Lecon.objects.all(), self.buyer).values_list("pk", flat=True))
        self.assertIn(self.paid_lesson.pk, ids)


class ParcoursQuizGatingTests(TestCase):
    """La soumission de quiz et l'API quiz ne doivent jamais exposer le
    contenu d'une leçon payante non acquise (mobile_education_quiz,
    mobile_education_submit_quiz, QuizViewSet)."""

    def setUp(self):
        organisation = Organisation.objects.create(nom="Org quiz", type="Université")
        self.creator = User.objects.create_user("quiz-creator", password="testpass")
        self.stranger = User.objects.create_user("quiz-stranger", password="testpass")
        self.parcours = Parcours.objects.create(
            organisation=organisation, created_by=self.creator, titre="Payant",
            description="...", niveau="Débutant", is_published=True, prix=Decimal("9.99"),
        )
        self.lesson = Lecon.objects.create(parcours=self.parcours, titre="L1", ordre=1)
        Quiz.objects.create(
            lecon=self.lesson, question="Q", choix_a="A", choix_b="B", bonne_reponse="A",
        )
        token, _ = Token.objects.get_or_create(user=self.stranger)
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

    def test_mobile_education_quiz_blocked_without_access(self):
        response = self.client.get(f"/api/mobile/education/lecons/{self.lesson.id}/quiz/")
        self.assertEqual(response.status_code, 402)

    def test_mobile_education_submit_quiz_blocked_without_access(self):
        response = self.client.post(
            f"/api/mobile/education/lecons/{self.lesson.id}/submit/",
            {"answers": {}}, format="json",
        )
        self.assertEqual(response.status_code, 402)

    def test_mobile_education_lecons_blocked_without_access(self):
        response = self.client.get(f"/api/mobile/education/parcours/{self.parcours.id}/lecons/")
        self.assertEqual(response.status_code, 402)
        self.assertEqual(response.json().get("code"), "payment_required")

    def test_mobile_education_projects_blocked_without_access(self):
        Project.objects.create(parcours=self.parcours, titre="Projet", description="...")
        response = self.client.get(f"/api/mobile/education/parcours/{self.parcours.id}/projects/")
        self.assertEqual(response.status_code, 402)

    def test_mobile_education_materiel_pdf_blocked_without_access(self):
        response = self.client.get(f"/api/mobile/education/parcours/{self.parcours.id}/materiel/pdf/")
        self.assertEqual(response.status_code, 402)
