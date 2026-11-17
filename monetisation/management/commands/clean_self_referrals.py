"""Corrige les auto-parrainages (un utilisateur enregistré comme son propre
parrain) et supprime les commissions qui n'auraient jamais dû exister.

    python manage.py clean_self_referrals          # simulation, ne change rien
    python manage.py clean_self_referrals --apply  # applique la correction

- auto-parrainage : le lien de parrainage est retiré et les commissions NON
  converties sont supprimées (celles déjà converties en crédits sont
  seulement signalées) ;
- commissions sans parrain : supprimées (l'ancien code en créait pour des
  utilisateurs inscrits sans code de parrainage ; personne ne les voyait).
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import F

from monetisation.models import Referral, ReferralTransaction


class Command(BaseCommand):
    help = "Retire les auto-parrainages et leurs commissions non converties."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Appliquer (sinon simple simulation).")

    def handle(self, *args, **options):
        apply = options["apply"]
        self_refs = list(Referral.objects.filter(referrer_id=F("referred_id")).select_related("referred"))
        # Listées AVANT la correction : un auto-parrainage corrigé n'a plus de
        # parrain, ses commissions ne doivent pas être prises pour des orphelines.
        orphan_ids = list(
            ReferralTransaction.objects.filter(referral__referrer__isnull=True).values_list("pk", flat=True)
        )

        if not self_refs:
            self.stdout.write("Aucun auto-parrainage.")
        for ref in self_refs:
            pending = ReferralTransaction.objects.filter(referral=ref, converted=False)
            converted_count = ReferralTransaction.objects.filter(referral=ref, converted=True).count()
            points = round(sum(c.amount for c in pending), 2)
            line = (f"{ref.referred.username} est son propre parrain : "
                    f"{pending.count()} commission(s) non convertie(s), {points:g} points")
            if converted_count:
                line += f" ; {converted_count} déjà convertie(s) en crédits (laissées)"
            self.stdout.write(line)
            if apply:
                with transaction.atomic():
                    pending.delete()
                    ref.referrer = None
                    ref.save(update_fields=["referrer"])

        self.stdout.write(f"Commissions sans parrain : {len(orphan_ids)}")
        if apply and orphan_ids:
            ReferralTransaction.objects.filter(pk__in=orphan_ids).delete()

        if apply:
            self.stdout.write(self.style.SUCCESS("Correction appliquée."))
        else:
            self.stdout.write("Simulation uniquement : relancez avec --apply pour corriger.")
