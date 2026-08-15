from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from espcontrol.agent.agent import FounatekAgent
from espcontrol.models import AppareilData
import time
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = "Lance l'agent IA Founatek — déclenché dès réception de données"

    def handle(self, *args, **options):
        User = get_user_model()
        self.stdout.write(
            "🚀 Agent FOUNATEK NEXUS — mode événementiel (trigger sur nouvelles données)"
        )

        # ── Mémorise le dernier ID traité par user ────────────────
        # { user_id: dernier_appareildata_id_traité }
        last_seen = {}

        while True:
            try:
                users = User.objects.filter(
                    is_active=True
                ).exclude(devices__isnull=True).distinct()

                for user in users:
                    # Récupère la dernière donnée de ce user
                    latest = AppareilData.objects.filter(
                        device__user=user
                    ).order_by('-received_at').first()

                    if not latest:
                        continue

                    # ── NOUVEAU ? ─────────────────────────────────
                    # Compare avec le dernier ID traité
                    last_id = last_seen.get(user.id, None)

                    if latest.id != last_id:
                        # Nouvelle donnée détectée → lance l'agent
                        last_seen[user.id] = latest.id

                        self.stdout.write(
                            f"📡 Nouvelle donnée détectée pour "
                            f"{user.username} "
                            f"(ID={latest.id}) → agent lancé"
                        )

                        agent  = FounatekAgent(user)
                        report = agent.run()

                        if report['decisions']:
                            self.stdout.write(
                                self.style.SUCCESS(
                                    f"⚡ {user.username} → "
                                    f"{len(report['decisions'])} actions"
                                )
                            )
                        else:
                            self.stdout.write(
                                f"✅ {user.username} → aucune action nécessaire"
                            )
                    # Si même ID → rien de nouveau → on skip silencieusement

            except Exception as e:
                self.stdout.write(self.style.ERROR(f"❌ Erreur : {e}"))
                logger.error(f"Erreur agent : {e}")
                time.sleep(5)
                continue

            # ── Polling léger ─────────────────────────────────────
            # Vérifie toutes les 0.5s si nouvelles données
            # Beaucoup plus léger que 1s car ne lance l'agent
            # QUE si nouvelle donnée détectée
            time.sleep(0.5)