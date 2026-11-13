from datetime import timedelta
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from espcontrol.models import AppareilData, Device

User = get_user_model()


class PurgeOldSensorDataTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="purge-user", password="x")
        self.device = Device.objects.create(user=self.user, device_id="purge-dev", name="Capteur purge")

    def _create_reading(self, when, **payload):
        row = AppareilData.objects.create(device=self.device, payload=payload)
        AppareilData.objects.filter(pk=row.pk).update(received_at=when)
        return row

    def test_old_readings_in_same_hour_are_compressed_to_one_average(self):
        # Plan free -> history_days = 1, donc tout ce qui a plus d'un jour est compressible.
        old_hour = timezone.now() - timedelta(days=5)
        hour_start = old_hour.replace(minute=0, second=0, microsecond=0)
        self._create_reading(hour_start + timedelta(minutes=5), temperature=20.0, humidity=50)
        self._create_reading(hour_start + timedelta(minutes=35), temperature=22.0, humidity=60)

        call_command("purge_old_sensor_data", stdout=StringIO())

        remaining = AppareilData.objects.filter(device=self.device)
        self.assertEqual(remaining.count(), 1)
        summary = remaining.first()
        self.assertTrue(summary.is_hourly_average)
        self.assertEqual(summary.payload["temperature"], 21.0)
        self.assertEqual(summary.payload["humidity"], 55)
        self.assertEqual(summary.received_at, hour_start)

    def test_recent_readings_within_history_window_are_untouched(self):
        self._create_reading(timezone.now() - timedelta(hours=2), temperature=20.0)
        self._create_reading(timezone.now() - timedelta(hours=1), temperature=21.0)

        call_command("purge_old_sensor_data", stdout=StringIO())

        self.assertEqual(AppareilData.objects.filter(device=self.device, is_hourly_average=False).count(), 2)

    def test_single_old_reading_in_an_hour_is_left_alone(self):
        old_hour = timezone.now() - timedelta(days=5)
        self._create_reading(old_hour, temperature=20.0)

        call_command("purge_old_sensor_data", stdout=StringIO())

        remaining = AppareilData.objects.filter(device=self.device)
        self.assertEqual(remaining.count(), 1)
        self.assertFalse(remaining.first().is_hourly_average)

    def test_already_averaged_rows_are_never_reprocessed(self):
        old_hour = timezone.now() - timedelta(days=5)
        hour_start = old_hour.replace(minute=0, second=0, microsecond=0)
        row = AppareilData.objects.create(device=self.device, payload={"temperature": 21.0}, is_hourly_average=True)
        AppareilData.objects.filter(pk=row.pk).update(received_at=hour_start)

        call_command("purge_old_sensor_data", stdout=StringIO())

        self.assertEqual(AppareilData.objects.filter(device=self.device).count(), 1)

    def test_dry_run_does_not_modify_data(self):
        old_hour = timezone.now() - timedelta(days=5)
        hour_start = old_hour.replace(minute=0, second=0, microsecond=0)
        self._create_reading(hour_start + timedelta(minutes=5), temperature=20.0)
        self._create_reading(hour_start + timedelta(minutes=35), temperature=22.0)

        call_command("purge_old_sensor_data", "--dry-run", stdout=StringIO())

        self.assertEqual(AppareilData.objects.filter(device=self.device, is_hourly_average=False).count(), 2)
