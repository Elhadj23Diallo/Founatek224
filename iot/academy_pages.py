"""Vitrine du Livre 1, sans publication automatique des contenus."""
from django.conf import settings
from django.shortcuts import render

from .academy_access import can_read_book_chapter, has_full_access
from .book_catalog import BOOK_SLUG, CHAPTERS, PACK_PRICE_EUR
from .models import AcademyBookLesson, Parcours


def academy_book_home(request):
    is_admin = has_full_access(request.user)
    counts = {}
    for row in AcademyBookLesson.objects.filter(published=True).values_list("chapter_number", flat=True):
        counts[row] = counts.get(row, 0) + 1
    drafts = {}
    admin_parcours = None
    if is_admin:
        for row in AcademyBookLesson.objects.filter(published=False).values_list("chapter_number", flat=True):
            drafts[row] = drafts.get(row, 0) + 1
        admin_parcours = Parcours.objects.filter(slug=BOOK_SLUG).first()
    chapters = [
        {
            "number": number,
            "title": title,
            "free": free,
            "available": bool(counts.get(number)),
            "lessons_count": counts.get(number, 0),
            "unlocked": can_read_book_chapter(request.user, number),
            "drafts_count": drafts.get(number, 0),
        }
        for number, title, free in CHAPTERS
    ]
    return render(request, "iot/academy_book_home.html", {
        "chapters": chapters,
        "price": PACK_PRICE_EUR,
        "book_slug": BOOK_SLUG,
        "is_admin": is_admin,
        "admin_parcours": admin_parcours,
        "checkout_enabled": bool(getattr(settings, "ACADEMY_BOOK_CHECKOUT_ENABLED", False))
            and bool(getattr(settings, "STRIPE_ENABLED", False)),
    })
