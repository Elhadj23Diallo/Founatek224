from collections import defaultdict
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from espcontrol.models import AppareilData, Device
from monetisation.utils import get_plan_limits


def _hour_bucket(dt):
    return dt.replace(minute=0, second=0, microsecond=0)


def _average_payloads(payloads):
    """Moyenne chaque champ numérique présent dans au moins un payload du
    groupe ; pour un champ non numérique, garde la valeur du payload le plus
    récent (ex: un nom de capteur, un statut texte)."""
    numeric_sums = defaultdict(float)
    numeric_counts = defaultdict(int)
    last_values = {}

    for payload in payloads:
        for key, value in payload.items():
            last_values[key] = value
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                numeric_sums[key] += value
                numeric_counts[key] += 1

    averaged = dict(last_values)
    for key, total in numeric_sums.items():
        averaged[key] = round(total / numeric_counts[key], 4)
    return averaged


class Command(BaseCommand):
    help = (
        "Compresse les mesures AppareilData plus vieilles que la durée d'historique "
        "du plan de l'utilisateur en une moyenne par heure, au lieu de les garder "
        "à la résolution brute indéfiniment (ou de les supprimer)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Affiche ce qui serait fait sans modifier la base.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        now = timezone.now()
        total_compressed_hours = 0
        total_rows_removed = 0

        for device in Device.objects.select_related("user").all():
            history_days = get_plan_limits(device.user)["history_days"]
            cutoff = now - timedelta(days=history_days)

            raw_old = (
                AppareilData.objects
                .filter(device=device, is_hourly_average=False, received_at__lt=cutoff)
                .order_by("received_at")
            )
            if not raw_old.exists():
                continue

            by_hour = defaultdict(list)
            for row in raw_old:
                by_hour[_hour_bucket(row.received_at)].append(row)

            for hour, rows in by_hour.items():
                if len(rows) <= 1:
                    # Rien à compresser pour cette heure-là (déjà une seule mesure).
                    continue

                total_compressed_hours += 1
                total_rows_removed += len(rows)

                if dry_run:
                    self.stdout.write(
                        f"[dry-run] {device.device_id} @ {hour}: {len(rows)} mesures -> 1 moyenne"
                    )
                    continue

                averaged_payload = _average_payloads([r.payload for r in rows])
                with transaction.atomic():
                    AppareilData.objects.filter(pk__in=[r.pk for r in rows]).delete()
                    summary = AppareilData.objects.create(
                        device=device,
                        payload=averaged_payload,
                        is_hourly_average=True,
                        is_anomaly=False,
                    )
                    # received_at est auto_now_add=True (forcé à "maintenant" à la
                    # création) : on le recale sur l'heure réelle via un UPDATE,
                    # qui ne repasse pas par la logique auto_now_add du save().
                    AppareilData.objects.filter(pk=summary.pk).update(received_at=hour)

        if dry_run:
            self.stdout.write(self.style.WARNING(
                f"[dry-run] {total_compressed_hours} heures seraient compressées "
                f"({total_rows_removed} mesures brutes -> {total_compressed_hours} moyennes)."
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                f"✅ {total_compressed_hours} heures compressées "
                f"({total_rows_removed} mesures brutes -> {total_compressed_hours} moyennes)."
            ))
