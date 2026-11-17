"""Importer sans publication les fiches disponibles du Livre 1 depuis les extraits Canva.

Usage : python manage.py import_academy_full_book
        python manage.py import_academy_full_book --apply
Ne supprime ni ne modifie les leçons existantes, les quiz ou les progressions.
"""
import json
import re
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from iot.book_catalog import BOOK_SLUG
from iot.models import AcademyBookLesson, BlocPedagogique, Lecon, Parcours


SOURCE = Path(__file__).resolve().parents[2] / "academy_source"


class Command(BaseCommand):
    help = "Créer en brouillon les fiches disponibles du livre Canva, sans publication ni paiement."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Créer les brouillons")

    def handle(self, *args, **options):
        parcours = Parcours.objects.filter(slug=BOOK_SLUG).first()
        if parcours is None:
            raise CommandError("Parcours introuvable : exécutez prepare_academy_book.")
        created = skipped = 0
        for path in sorted(SOURCE.glob("chapter_*.json")):
            entries = json.loads(path.read_text(encoding="utf-8"))
            for entry in entries:
                number = entry["id"]
                chapter = number.split(".")[0].zfill(2)
                title = f'{number} — {entry["title"]}'
                if AcademyBookLesson.objects.filter(
                    lecon__parcours=parcours, lecon__titre__startswith=f"{number} —"
                ).exists() or Lecon.objects.filter(
                    parcours=parcours, titre__startswith=f"{number} —"
                ).exists():
                    skipped += 1
                    continue
                self.stdout.write(f"Brouillon : {title}")
                if not options["apply"]:
                    continue
                body = entry["body"]
                # Les extraits restent des supports de travail, pas des fiches relues.
                body = re.sub(r"\\n{3,}", "\\n\\n", body).strip()
                if len(body) < 100:
                    self.stdout.write(self.style.WARNING(f"Source trop courte : {number}"))
                    continue
                major, minor = map(int, number.split("."))
                with transaction.atomic():
                    lecon = Lecon.objects.create(
                        parcours=parcours,
                        titre=title[:200],
                        ordre=major * 100 + minor,
                        resume="Fiche issue du Livre 1 Canva, à relire et enrichir avant publication.",
                        duree_minutes=20,
                    )
                    AcademyBookLesson.objects.create(
                        lecon=lecon, chapter_number=chapter, published=False
                    )
                    BlocPedagogique.objects.create(
                        lecon=lecon, ordre=1, type="texte", contenu=body
                    )
                    created += 1
        self.stdout.write(self.style.SUCCESS(
            f"Fiches créées : {created} ; existantes ignorées : {skipped}. "
            "Toutes les nouvelles fiches restent en brouillon, sans quiz validé. "
            "Les chapitres absents de la source doivent être rédigés séparément."
        ))
