"""Seed non destructif du parcours ESP32 interactif de Founatek Academy.

Usage : python manage.py seed_esp32_wokwi [--username elhadj]

La commande est idempotente. Elle conserve les progressions et les contenus
additionnels, et n'efface aucune leçon, aucun bloc, aucun quiz ni projet.
"""

import os

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from iot.course_data.esp32_fondamentaux import COURSE
from iot.models import (
    FormateurProfile,
    BlocPedagogique,
    Lecon,
    Organisation,
    Parcours,
    Project,
    Quiz,
)


class Command(BaseCommand):
    help = "Ajoute ou met à jour le parcours ESP32/Wokwi sans supprimer de données."

    def add_arguments(self, parser):
        parser.add_argument(
            "--username",
            default=os.environ.get("FOUNATEK_SEED_USERNAME", "elhadj"),
            help="Compte Django créateur du parcours (défaut : elhadj).",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        username = options["username"]
        formateur = User.objects.filter(username=username).first()
        if formateur is None:
            raise CommandError(
                f"Utilisateur Django {username!r} introuvable; aucun changement n'a été effectué."
            )

        organisation = Organisation.objects.filter(nom="Founatek Academy").first()
        if organisation is None and hasattr(formateur, "formateur_profile"):
            organisation = formateur.formateur_profile.organisation
        if organisation is None:
            organisation = Organisation.objects.first()
        organisation_creee = False
        if organisation is None:
            organisation = Organisation.objects.create(
                nom="Founatek Academy",
                type="Entreprise",
            )
            organisation_creee = True
        _, profil_cree = FormateurProfile.objects.get_or_create(
            user=formateur,
            defaults={"organisation": organisation},
        )

        defaults = {
            "organisation": organisation,
            "created_by": formateur,
            "titre": COURSE["titre"],
            "description": COURSE["description"],
            "niveau": COURSE["niveau"],
            "prix": COURSE["prix"],
            "certifiant": COURSE["certifiant"],
            "is_published": True,
            "materiel_requis": COURSE["materiel_requis"],
        }
        parcours, parcours_cree = Parcours.objects.get_or_create(
            slug=COURSE["slug"],
            defaults=defaults,
        )
        if not parcours_cree:
            if parcours.titre != COURSE["titre"]:
                raise CommandError(
                    f"Le slug {COURSE['slug']!r} appartient déjà à un autre parcours; arrêt sans écriture."
                )
            # Conserver l'état de publication et le propriétaire si un formateur
            # les a modifiés après la création initiale.
            for field in (
                "organisation",
                "titre",
                "description",
                "niveau",
                "prix",
                "certifiant",
                "materiel_requis",
            ):
                setattr(parcours, field, defaults[field])
            parcours.save(update_fields=[
                "organisation",
                "titre",
                "description",
                "niveau",
                "prix",
                "certifiant",
                "materiel_requis",
            ])

        lecons_creees = 0
        blocs_crees = 0
        quiz_crees = 0
        for lesson_data in COURSE["lessons"]:
            lecon, created = self._upsert_one(
                Lecon,
                {"parcours": parcours, "ordre": lesson_data["ordre"]},
                {
                    "titre": lesson_data["titre"],
                    "resume": lesson_data["resume"],
                    "duree_minutes": lesson_data["duree_minutes"],
                },
                label=f"leçon {lesson_data['ordre']}",
            )
            lecons_creees += int(created)

            for ordre_bloc, block_data in enumerate(lesson_data["blocs"], start=1):
                _, created = self._upsert_one(
                    BlocPedagogique,
                    {"lecon": lecon, "ordre": ordre_bloc},
                    {
                        "type": block_data["type"],
                        "contenu": block_data.get("contenu"),
                        "language": block_data.get("language"),
                        "code": block_data.get("code"),
                    },
                    label=f"bloc {ordre_bloc} de la leçon {lesson_data['ordre']}",
                )
                blocs_crees += int(created)

            for quiz_data in lesson_data.get("quiz", []):
                question = quiz_data["question"]
                _, created = self._upsert_one(
                    Quiz,
                    {"lecon": lecon, "question": question},
                    {
                        "choix_a": quiz_data["a"],
                        "choix_b": quiz_data["b"],
                        "choix_c": quiz_data.get("c"),
                        "choix_d": quiz_data.get("d"),
                        "bonne_reponse": quiz_data["bonne"],
                        "plusieurs_reponses": quiz_data.get("plusieurs", False),
                        "explication": quiz_data.get("explication", ""),
                    },
                    label=f"question de quiz de la leçon {lesson_data['ordre']}",
                )
                quiz_crees += int(created)

        project_data = COURSE["project"]
        _, projet_cree = self._upsert_one(
            Project,
            {"parcours": parcours, "titre": project_data["titre"]},
            {
                "ordre": project_data["ordre"],
                "language": project_data["language"],
                "description": project_data["description"],
                "code": project_data["code"],
            },
            label="projet final",
        )

        action = "créé" if parcours_cree else "mis à jour"
        self.stdout.write(self.style.SUCCESS(
            f"Parcours {action} : {parcours.titre} (id={parcours.pk}, publié={parcours.is_published})."
        ))
        self.stdout.write(
            f"Leçons ajoutées : {lecons_creees}; blocs ajoutés : {blocs_crees}; "
            f"questions ajoutées : {quiz_crees}; projet final {'ajouté' if projet_cree else 'actualisé'}."
        )
        if organisation_creee:
            self.stdout.write("Organisation Founatek Academy créée.")
        if profil_cree:
            self.stdout.write(f"Profil formateur créé pour {formateur.username}.")
        self.stdout.write(
            "Les progressions, médias et contenus hors seed n'ont pas été supprimés."
        )

    def _upsert_one(self, model, lookup, defaults, label):
        """Upsert unique, avec arrêt explicite si les données contiennent des doublons."""
        queryset = model.objects.filter(**lookup)
        count = queryset.count()
        if count > 1:
            raise CommandError(
                f"Plusieurs enregistrements correspondent à {label}; "
                "aucune suppression automatique n'est tentée."
            )

        if count == 1:
            instance = queryset.first()
            for field, value in defaults.items():
                setattr(instance, field, value)
            if defaults:
                instance.save(update_fields=list(defaults))
            return instance, False

        return model.objects.create(**lookup, **defaults), True
