"""Création prudente du parcours Livre 1 en brouillon.

Exemple:
 python manage.py prepare_academy_book --username elhadj
 python manage.py prepare_academy_book --username elhadj --apply
"""
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from iot.book_catalog import BOOK_SLUG
from iot.models import Parcours


class Command(BaseCommand):
    help = "Prépare le parcours Livre 1 sans publier de cours ni déclencher de paiement."

    def add_arguments(self, parser):
        parser.add_argument("--username", required=True, help="Nom exact du compte formateur")
        parser.add_argument("--apply", action="store_true", help="Enregistrer le brouillon (sinon simulation)")

    def handle(self, *args, **options):
        username = options["username"]
        user = get_user_model().objects.filter(username=username).first()
        if user is None:
            raise CommandError(f"Compte '{username}' introuvable. Aucun changement.")
        try:
            organisation = user.formateur_profile.organisation
        except Exception:
            raise CommandError("Ce compte ne possède pas de profil formateur avec organisation. Aucun changement.")

        existing = Parcours.objects.filter(slug=BOOK_SLUG).first()
        if existing:
            if existing.created_by_id != user.pk:
                raise CommandError("Ce parcours appartient déjà à un autre formateur. Aucun changement.")
            self.stdout.write(self.style.SUCCESS(
                f"Parcours déjà présent (ID {existing.pk}, publié={existing.is_published}). Aucune modification."
            ))
            return

        self.stdout.write(f"Création envisagée : Livre 1 pour {username} / {organisation.nom} (brouillon).")
        if not options["apply"]:
            self.stdout.write(self.style.WARNING("Simulation uniquement. Ajoutez --apply pour enregistrer."))
            return

        with transaction.atomic():
            parcours, created = Parcours.objects.get_or_create(
                slug=BOOK_SLUG,
                defaults={
                    "titre": "Le catalogue de l'électronique embarquée — Livre 1",
                    "description": (
                        "Les composants et les capteurs, fiche par fiche. "
                        "Les bases sont gratuites ; les autres chapitres seront "
                        "progressivement proposés après validation pédagogique."
                    ),
                    "organisation": organisation,
                    "created_by": user,
                    "niveau": "Débutant",
                    "prix": 0,
                    "certifiant": False,
                    "is_published": False,
                },
            )
            if not created:
                raise CommandError("Un parcours portant ce slug a été créé entre-temps. Aucun changement.")
        self.stdout.write(self.style.SUCCESS(
            f"Brouillon créé (ID {parcours.pk}). Aucune leçon publiée, aucun paiement activé."
        ))
