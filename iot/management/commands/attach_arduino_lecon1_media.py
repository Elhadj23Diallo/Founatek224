"""
Attache les vraies images a la Lecon 1 du parcours "Initiation a l'Electronique
de base avec Arduino" (photo du kit + schema de progression des 3 parcours),
en remplacement des emplacements reserves crees par seed_arduino_debutant.

Les fichiers sources vivent dans iot/course_media/arduino_debutant/ (verses au
depot Git), donc cette commande est rejouable partout ou le code est deploye
(local ou PythonAnywhere) sans dependre d'un chemin propre a une machine.

Usage : python manage.py attach_arduino_lecon1_media
"""
import os
from django.conf import settings
from django.core.files import File
from django.core.management.base import BaseCommand
from iot.models import Parcours, BlocPedagogique

ASSETS_DIR = os.path.join(settings.BASE_DIR, "iot", "course_media", "arduino_debutant")

KIT_CONTENU = "Photo du kit complet utilisé pour ce cours (kit Smraza)."
PROGRESSION_CONTENU = (
    "Schéma de progression des 3 parcours Founatek Academy : Arduino de base "
    "(ce parcours) → Électronique embarquée (station connectée) → Domotique "
    "(maison intelligente), chaque étage supposant le précédent acquis."
)


class Command(BaseCommand):
    help = "Attache les images reelles a la Lecon 1 du parcours Arduino debutant"

    def handle(self, *args, **options):
        parcours = Parcours.objects.filter(
            titre="Initiation à l'Électronique de base avec Arduino"
        ).first()
        if not parcours:
            self.stdout.write(self.style.ERROR(
                "Parcours introuvable — lance d'abord : python manage.py seed_arduino_debutant"
            ))
            return

        lecon1 = parcours.lecons.filter(ordre=1).first()
        if not lecon1:
            self.stdout.write(self.style.ERROR("Leçon 1 introuvable."))
            return

        # Idempotent par construction : on supprime tous les blocs image de
        # cette leçon puis on recrée exactement les deux attendus, plutôt que
        # d'essayer de deviner "lequel est déjà là" à partir de son ordre —
        # source d'un doublon si la commande est relancée après une modif
        # manuelle intermédiaire (vécu lors du premier essai).
        lecon1.blocs.filter(type="image").delete()

        diagram_bloc = BlocPedagogique.objects.create(
            lecon=lecon1, ordre=3, type="image", contenu=PROGRESSION_CONTENU
        )
        self._attach_file(diagram_bloc, "lecon1_progression.png")
        self.stdout.write(self.style.SUCCESS(f"Schéma de progression attaché (bloc id={diagram_bloc.id}, ordre=3)."))

        kit_bloc = BlocPedagogique.objects.create(
            lecon=lecon1, ordre=4, type="image", contenu=KIT_CONTENU
        )
        self._attach_file(kit_bloc, "lecon1_kit.jpg")
        self.stdout.write(self.style.SUCCESS(f"Photo du kit attachée (bloc id={kit_bloc.id}, ordre=4)."))

        self.stdout.write(self.style.SUCCESS("\nLeçon 1 à jour : texte, texte, schéma progression, photo kit."))

    def _attach_file(self, bloc, filename):
        path = os.path.join(ASSETS_DIR, filename)
        with open(path, "rb") as f:
            bloc.media_file.save(filename, File(f), save=False)
        bloc.save()
