from django.core.management.base import BaseCommand
from django.utils import timezone
from monetisation.models import UsageLog

class Command(BaseCommand):
    help = "Reset des quotas journaliers (API calls / devices) chaque jour"

    def handle(self, *args, **kwargs):
        today = timezone.now().date()

        # Supprimer les usages des jours précédents
        UsageLog.objects.filter(date__lt=today).delete()

        self.stdout.write(self.style.SUCCESS("✔️ Quotas journaliers réinitialisés (UsageLog nettoyé)"))
