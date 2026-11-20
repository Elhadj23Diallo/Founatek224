"""Contrôle des droits d'accès au pack Livre 1.

Aucun accès n'est attribué ici : un paiement doit être vérifié côté serveur.
"""
from .book_catalog import BOOK_SLUG, chapter_is_free
from .models import AcademyPackAccess, AcademyBookLesson


def can_read_book_chapter(user, chapter_number):
    if chapter_is_free(chapter_number):
        return True
    if not user or not user.is_authenticated:
        return False
    return AcademyPackAccess.objects.filter(
        user=user, pack_slug=BOOK_SLUG, active=True, revoked_at__isnull=True
    ).exists()


def can_read_lesson(user, lesson):
    """Fiches Livre 1 privées par défaut ; leçons ordinaires soumises au
    paywall générique de leur parcours (voir parcours_access.py)."""
    from .parcours_access import can_read_parcours
    try:
        entry = lesson.academy_book_entry
    except AcademyBookLesson.DoesNotExist:
        return can_read_parcours(user, lesson.parcours)
    if not entry.published:
        # Brouillon : visible seulement par l'équipe (relecture avant publication).
        return bool(user and user.is_authenticated and user.is_staff)
    return can_read_book_chapter(user, entry.chapter_number)


def filter_readable_lessons(queryset, user):
    """Filtre ORM appliqué avant sérialisation et accès aux blocs/quiz."""
    from django.db.models import Q
    from .book_catalog import FREE_CHAPTER, BOOK_SLUG
    from .parcours_access import readable_parcours_filter
    allowed = (Q(academy_book_entry__isnull=True) & readable_parcours_filter(user)) | Q(
        academy_book_entry__published=True,
        academy_book_entry__chapter_number=FREE_CHAPTER,
    )
    if user and user.is_authenticated and AcademyPackAccess.objects.filter(
        user=user, pack_slug=BOOK_SLUG, active=True, revoked_at__isnull=True
    ).exists():
        allowed |= Q(academy_book_entry__published=True)
    return queryset.filter(allowed)
