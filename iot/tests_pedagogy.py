from django.contrib.auth import get_user_model
from django.test import TestCase

from .book_catalog import BOOK_SLUG
from .models import AcademyBookLesson, Lecon, Organisation, Parcours, Progression
from .utils.pedagogy import lecon_est_debloquee, lecon_precedente

User = get_user_model()


class LeconPrecedenteSkipsUnpublishedDraftsTests(TestCase):
    """Un brouillon Livre 1 (fiche enrichie pas encore publiée, ou fiche brute
    jamais publiable) ne doit jamais bloquer pour toujours la suite : personne
    ne peut la valider, donc le déblocage séquentiel doit l'ignorer."""

    def setUp(self):
        self.user = User.objects.create_user("pedagogy-user", password="testpass")
        organisation = Organisation.objects.create(nom="Org pedagogy", type="Université")
        self.parcours = Parcours.objects.create(
            organisation=organisation, created_by=self.user, titre="Livre test",
            description="...", niveau="Débutant", is_published=True, slug=BOOK_SLUG,
        )
        self.l1 = Lecon.objects.create(parcours=self.parcours, titre="0.1", ordre=1)
        self.l2 = Lecon.objects.create(parcours=self.parcours, titre="0.2", ordre=2)
        self.draft_a = Lecon.objects.create(parcours=self.parcours, titre="0.3 brouillon", ordre=3)
        self.draft_b = Lecon.objects.create(parcours=self.parcours, titre="1.1 brouillon", ordre=101)
        self.l3 = Lecon.objects.create(parcours=self.parcours, titre="2.1", ordre=201)
        AcademyBookLesson.objects.create(lecon=self.l1, chapter_number="00", published=True)
        AcademyBookLesson.objects.create(lecon=self.l2, chapter_number="00", published=True)
        AcademyBookLesson.objects.create(lecon=self.draft_a, chapter_number="00", published=False)
        AcademyBookLesson.objects.create(lecon=self.draft_b, chapter_number="01", published=False)
        AcademyBookLesson.objects.create(lecon=self.l3, chapter_number="02", published=True)

    def test_precedente_skips_unpublished_drafts(self):
        self.assertEqual(lecon_precedente(self.l3), self.l2)

    def test_locked_until_last_published_lesson_completed(self):
        self.assertFalse(lecon_est_debloquee(self.user, self.l3))

    def test_unlocked_once_last_published_lesson_completed(self):
        Progression.objects.create(user=self.user, lecon=self.l2, completed=True, score=100)
        self.assertTrue(lecon_est_debloquee(self.user, self.l3))

    def test_draft_completion_is_irrelevant(self):
        """Même si un brouillon avait une Progression (ne devrait jamais arriver
        en pratique), ce n'est pas lui qui compte pour débloquer la suite."""
        Progression.objects.create(user=self.user, lecon=self.draft_a, completed=True, score=100)
        Progression.objects.create(user=self.user, lecon=self.draft_b, completed=True, score=100)
        self.assertFalse(lecon_est_debloquee(self.user, self.l3))

    def test_non_academy_lessons_unaffected(self):
        """Un parcours ordinaire (hors Livre 1) n'a pas de fiches 'brouillon' :
        le comportement reste simplement 'leçon juste avant'."""
        ordinary = Parcours.objects.create(
            organisation=self.parcours.organisation, created_by=self.user, titre="Cours normal",
            description="...", niveau="Débutant", is_published=True,
        )
        a = Lecon.objects.create(parcours=ordinary, titre="A", ordre=1)
        b = Lecon.objects.create(parcours=ordinary, titre="B", ordre=2)
        self.assertEqual(lecon_precedente(b), a)
