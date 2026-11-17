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
    """Leçons ordinaires inchangées ; fiches Livre 1 privées par défaut."""
    try:
        entry = lesson.academy_book_entry
    except AcademyBookLesson.DoesNotExist:
        return True
    if not entry.published:
        return False
    return can_read_book_chapter(user, entry.chapter_number)


def filter_readable_lessons(queryset, user):
    """Filtre ORM appliqué avant sérialisation et accès aux blocs/quiz."""
    from django.db.models import Q
    from .book_catalog import FREE_CHAPTER, BOOK_SLUG
    allowed = Q(academy_book_entry__isnull=True) | Q(
        academy_book_entry__published=True,
        academy_book_entry__chapter_number=FREE_CHAPTER,
    )
    if user and user.is_authenticated and AcademyPackAccess.objects.filter(
        user=user, pack_slug=BOOK_SLUG, active=True, revoked_at__isnull=True
    ).exists():
        allowed |= Q(academy_book_entry__published=True)
    return queryset.filter(allowed)
