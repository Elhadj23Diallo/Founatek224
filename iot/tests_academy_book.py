from django.contrib.auth import get_user_model
from django.test import TestCase

from .academy_access import can_read_book_chapter
from .book_catalog import BOOK_SLUG, PACK_PRICE_EUR, ordered_chapters
from .models import AcademyPackAccess


class AcademyBookAccessTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="academy_learner", password="test-password")

    def test_catalog_has_twelve_chapters_in_order(self):
        chapters = ordered_chapters()
        self.assertEqual([c["number"] for c in chapters], [f"{n:02d}" for n in range(12)])
        self.assertEqual(PACK_PRICE_EUR, 9.99)

    def test_basics_are_free(self):
        self.assertTrue(can_read_book_chapter(self.user, "00"))
        self.assertTrue(can_read_book_chapter(None, "00"))

    def test_paid_chapters_are_closed_without_entitlement(self):
        self.assertFalse(can_read_book_chapter(self.user, "01"))
        self.assertFalse(can_read_book_chapter(self.user, "11"))
        self.assertFalse(can_read_book_chapter(None, "01"))

    def test_inactive_and_revoked_access_do_not_unlock(self):
        access = AcademyPackAccess.objects.create(
            user=self.user, pack_slug=BOOK_SLUG, provider="admin", active=False
        )
        self.assertFalse(can_read_book_chapter(self.user, "02"))
        access.active = True
        access.save(update_fields=["active"])
        self.assertTrue(can_read_book_chapter(self.user, "02"))
        from django.utils import timezone
        access.revoked_at = timezone.now()
        access.save(update_fields=["revoked_at"])
        self.assertFalse(can_read_book_chapter(self.user, "02"))
