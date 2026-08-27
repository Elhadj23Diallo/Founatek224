"""
Attache le contenu interactif et les images reelles a la Lecon 2 du parcours
"Initiation a l'Electronique de base avec Arduino" (simulateur HTML de la loi
d'Ohm + deux chartes de couleurs de resistances), en remplacement de
l'emplacement reserve cree par seed_arduino_debutant.

Les fichiers sources vivent dans iot/course_media/arduino_debutant/ (verses au
depot Git), donc cette commande est rejouable partout ou le code est deploye
(local ou PythonAnywhere) sans dependre d'un chemin propre a une machine.

Usage : python manage.py attach_arduino_lecon2_media
"""
import os
from django.conf import settings
from django.core.files import File
from django.core.management.base import BaseCommand
from iot.models import Parcours, BlocPedagogique

ASSETS_DIR = os.path.join(settings.BASE_DIR, "iot", "course_media", "arduino_debutant")

INTERACTIF_CONTENU = (
    "Simulateur interactif — loi d'Ohm : fais varier la tension et la "
    "résistance avec les curseurs pour voir le courant changer en direct "
    "(analogie du réservoir d'eau)."
)
CHART_CONTENU = (
    "Table de correspondance des couleurs de résistances (4 bandes) — pour "
    "lire directement la valeur d'une résistance sur le composant, sans "
    "multimètre."
)
BANDS_CONTENU = (
    "Anatomie d'une résistance à 4 bandes : 1er chiffre, 2e chiffre, "
    "multiplicateur, tolérance — les mêmes bandes que celles du tableau "
    "précédent, appliquées sur un vrai composant."
)


class Command(BaseCommand):
    help = "Attache le simulateur loi d'Ohm et les chartes résistances à la Leçon 2 du parcours Arduino débutant"

    def handle(self, *args, **options):
        parcours = Parcours.objects.filter(
            titre="Initiation à l'Électronique de base avec Arduino"
        ).first()
        if not parcours:
            self.stdout.write(self.style.ERROR(
                "Parcours introuvable — lance d'abord : python manage.py seed_arduino_debutant"
            ))
            return

        lecon2 = parcours.lecons.filter(ordre=2).first()
        if not lecon2:
            self.stdout.write(self.style.ERROR("Leçon 2 introuvable."))
            return

        # Idempotent par construction : on supprime les blocs image/interactif
        # existants puis on recrée exactement les trois attendus (même idiome
        # que attach_arduino_lecon1_media), plutôt que de deviner "lequel est
        # déjà là" à partir de son ordre.
        lecon2.blocs.filter(type__in=["image", "interactif"]).delete()

        ohm_bloc = BlocPedagogique.objects.create(
            lecon=lecon2, ordre=3, type="interactif",
            contenu=INTERACTIF_CONTENU, language="html",
        )
        ohm_bloc.code = self._read_text("lecon2_loi_ohm_interactif.html")
        ohm_bloc.save()
        self.stdout.write(self.style.SUCCESS(f"Simulateur loi d'Ohm attaché (bloc id={ohm_bloc.id}, ordre=3)."))

        chart_bloc = BlocPedagogique.objects.create(
            lecon=lecon2, ordre=4, type="image", contenu=CHART_CONTENU
        )
        self._attach_file(chart_bloc, "lecon2_resistor_chart.jpg")
        self.stdout.write(self.style.SUCCESS(f"Charte des couleurs attachée (bloc id={chart_bloc.id}, ordre=4)."))

        bands_bloc = BlocPedagogique.objects.create(
            lecon=lecon2, ordre=5, type="image", contenu=BANDS_CONTENU
        )
        self._attach_file(bands_bloc, "lecon2_resistor_bands.jpg")
        self.stdout.write(self.style.SUCCESS(f"Schéma des bandes attaché (bloc id={bands_bloc.id}, ordre=5)."))

        self.stdout.write(self.style.SUCCESS(
            "\nLeçon 2 à jour : texte, texte, simulateur loi d'Ohm, charte couleurs, schéma bandes."
        ))

    def _read_text(self, filename):
        path = os.path.join(ASSETS_DIR, filename)
        with open(path, "r", encoding="utf-8") as f:
            return f.read()

    def _attach_file(self, bloc, filename):
        path = os.path.join(ASSETS_DIR, filename)
        with open(path, "rb") as f:
            bloc.media_file.save(filename, File(f), save=False)
        bloc.save()
