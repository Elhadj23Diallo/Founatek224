"""Publier les fiches d'un chapitre du Livre 1, après vérification du contenu.

Usage :
  python manage.py publish_academy_chapter --chapter 01
  python manage.py publish_academy_chapter --chapter 01 --apply

Publication tout-ou-rien par chapitre : si une seule fiche du chapitre n'a
pas encore de contenu ou de quiz, rien n'est publié et la commande liste
ce qui manque.
"""
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from iot.book_catalog import BOOK_SLUG, CHAPTERS
from iot.models import AcademyBookLesson


VALID_CHAPTERS = {number for number, _, _ in CHAPTERS}


class Command(BaseCommand):
    help = "Publie les fiches d'un chapitre du Livre 1, après vérification contenu + quiz."

    def add_arguments(self, parser):
        parser.add_argument("--chapter", required=True, help="Numéro de chapitre, ex. 01")
        parser.add_argument("--apply", action="store_true", help="Publier réellement (sinon simulation)")

    def handle(self, *args, **options):
        chapter = options["chapter"].zfill(2)
        if chapter not in VALID_CHAPTERS:
            raise CommandError(f"Chapitre inconnu : {chapter}. Valeurs possibles : {sorted(VALID_CHAPTERS)}")

        entries = list(
            AcademyBookLesson.objects.select_related("lecon")
            .filter(lecon__parcours__slug=BOOK_SLUG, chapter_number=chapter)
            .order_by("lecon__ordre")
        )
        if not entries:
            raise CommandError(f"Aucune fiche trouvée pour le chapitre {chapter}. Importez-les d'abord.")

        ready, blocked = [], []
        for entry in entries:
            if entry.published:
                self.stdout.write(f"{entry.lecon.titre} : déjà publiée")
                continue
            missing = []
            if not entry.lecon.blocs.exists():
                missing.append("contenu")
            if not entry.lecon.quizzes.exists():
                missing.append("quiz")
            if missing:
                blocked.append((entry.lecon.titre, missing))
            else:
                ready.append(entry)

        for titre, missing in blocked:
            self.stdout.write(self.style.WARNING(f"Bloquée (il manque : {', '.join(missing)}) : {titre}"))
        for entry in ready:
            self.stdout.write(f"Prête à publier : {entry.lecon.titre}")

        if blocked:
            self.stdout.write(self.style.ERROR(
                f"{len(blocked)} fiche(s) non prête(s) pour le chapitre {chapter}. "
                "Ajoutez le contenu/quiz manquant avant de publier ce chapitre. Aucun changement."
            ))
            return

        if not ready:
            self.stdout.write("Rien à publier (déjà fait ou aucune fiche restante).")
            return

        if not options["apply"]:
            self.stdout.write(self.style.WARNING(
                f"Simulation uniquement : {len(ready)} fiche(s) seraient publiées. Relancez avec --apply."
            ))
            return

        with transaction.atomic():
            count = AcademyBookLesson.objects.filter(
                pk__in=[e.pk for e in ready], published=False
            ).update(published=True)
        self.stdout.write(self.style.SUCCESS(f"{count} fiche(s) du chapitre {chapter} publiée(s)."))
