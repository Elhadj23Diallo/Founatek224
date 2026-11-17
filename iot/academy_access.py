"""Contrôle des droits d'accès au pack Livre 1.

Aucun accès n'est attribué ici : un paiement doit être vérifié côté serveur.
"""
from .book_catalog import BOOK_SLUG, chapter_is_free
from .models import AcademyPackAccess


def can_read_book_chapter(user, chapter_number):
    if chapter_is_free(chapter_number):
        return True
    if not user or not user.is_authenticated:
        return False
    return AcademyPackAccess.objects.filter(
        user=user, pack_slug=BOOK_SLUG, active=True, revoked_at__isnull=True
    ).exists()
