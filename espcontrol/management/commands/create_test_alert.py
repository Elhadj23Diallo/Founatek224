"""Crée une alerte de test pour vérifier les notifications mobile (vibration
en premier plan + notification push si l'appareil est enregistré).

Usage :
  python manage.py create_test_alert --username elhadj
  python manage.py create_test_alert --username elhadj --level WARN --message "Test"
"""
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from espcontrol.models import AgentAlert

User = get_user_model()


class Command(BaseCommand):
    help = "Crée une AgentAlert de test pour un utilisateur donné."

    def add_arguments(self, parser):
        parser.add_argument("--username", required=True)
        parser.add_argument("--level", default="CRITICAL", choices=["INFO", "WARN", "CRITICAL"])
        parser.add_argument(
            "--message", default="Alerte de test — vous pouvez l'archiver ou la supprimer sans risque."
        )

    def handle(self, *args, **options):
        user = User.objects.filter(username=options["username"]).first()
        if user is None:
            raise CommandError(f"Utilisateur '{options['username']}' introuvable. Aucun changement.")
        alert = AgentAlert.objects.create(
            user=user, code="TEST_MANUAL", level=options["level"], message=options["message"],
        )
        self.stdout.write(self.style.SUCCESS(
            f"Alerte #{alert.id} créée pour {user.username} ({alert.level}). "
            "Ouvrez l'onglet Alertes sur le téléphone (rafraîchissement auto activé) "
            "ou attendez la notification push si l'appareil est enregistré."
        ))
