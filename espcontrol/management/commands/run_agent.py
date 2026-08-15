from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

from espcontrol.agent.agent import FounatekAgent


class Command(BaseCommand):
    help = "Lance l'agent IA Founatek automatiquement"

    def handle(self, *args, **options):
        User = get_user_model()

        for user in User.objects.filter(is_active=True):
            agent = FounatekAgent(user)
            report = agent.run()

            self.stdout.write(
                self.style.SUCCESS(
                    f"Agent exécuté pour {user.username} → {report['decisions']}"
                )
            )
