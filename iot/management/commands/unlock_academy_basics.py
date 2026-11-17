"""Publier explicitement les deux premières fiches gratuites après vérification.

Simulation : python manage.py unlock_academy_basics
Publication : python manage.py unlock_academy_basics --apply
"""
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from iot.book_catalog import BOOK_SLUG
from iot.models import AcademyBookLesson


TITLES = (
    "0.1 — Tension, courant et loi d'Ohm",
    "0.2 — Courant continu et alternatif",
)


class Command(BaseCommand):
    help = "Déverrouille uniquement les fiches 0.1 et 0.2 du chapitre 00 gratuit."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Confirmer la publication des deux fiches")

    def handle(self, *args, **options):
        entries = list(
            AcademyBookLesson.objects.select_related("lecon__parcours")
            .filter(lecon__parcours__slug=BOOK_SLUG, chapter_number="00", lecon__titre__in=TITLES)
        )
        if len(entries) != len(TITLES) or {e.lecon.titre for e in entries} != set(TITLES):
            raise CommandError("Les deux fiches attendues sont introuvables. Importez-les d'abord ; aucun changement.")
        for entry in entries:
            if not entry.lecon.blocs.exists() or not entry.lecon.quizzes.exists():
                raise CommandError(f"Contenu ou quiz manquant pour {entry.lecon.titre}. Aucun changement.")
        for entry in entries:
            self.stdout.write(f"{entry.lecon.titre} : {'déjà accessible' if entry.published else 'à déverrouiller'}")
        if not options["apply"]:
            self.stdout.write("Simulation uniquement. Vérifiez le contenu, puis relancez avec --apply.")
            return
        with transaction.atomic():
            count = AcademyBookLesson.objects.filter(pk__in=[e.pk for e in entries], published=False).update(published=True)
        self.stdout.write(self.style.SUCCESS(f"{count} fiche(s) rendue(s) accessible(s) gratuitement."))
