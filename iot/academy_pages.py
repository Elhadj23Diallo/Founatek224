"""Vitrine du Livre 1, sans publication automatique des contenus."""
from django.conf import settings
from django.shortcuts import render

from .academy_access import can_read_book_chapter
from .book_catalog import BOOK_SLUG, CHAPTERS, PACK_PRICE_EUR
from .models import AcademyBookLesson


def academy_book_home(request):
    counts = {}
    for row in AcademyBookLesson.objects.filter(published=True).values_list("chapter_number", flat=True):
        counts[row] = counts.get(row, 0) + 1
    chapters = [
        {
            "number": number,
            "title": title,
            "free": free,
            "available": bool(counts.get(number)),
            "lessons_count": counts.get(number, 0),
            "unlocked": can_read_book_chapter(request.user, number),
        }
        for number, title, free in CHAPTERS
    ]
    return render(request, "iot/academy_book_home.html", {
        "chapters": chapters,
        "price": PACK_PRICE_EUR,
        "book_slug": BOOK_SLUG,
        "checkout_enabled": bool(getattr(settings, "ACADEMY_BOOK_CHECKOUT_ENABLED", False))
            and bool(getattr(settings, "STRIPE_ENABLED", False)),
    })
