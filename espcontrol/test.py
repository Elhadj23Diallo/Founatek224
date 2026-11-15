# ...existing code...
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient
from espcontrol.models import Device, AppareilData, ActionLog

class IngestEndpointTest(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="testuser", password="pass")
        # Token de simulation (supprime l'éventuel token existant puis crée)
        self.token_key = "8cc82fc02b153388801241b9c71a268840f9945a"
        Token.objects.filter(user=self.user).delete()
        Token.objects.create(user=self.user, key=self.token_key)
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION="Token " + self.token_key)
        self.url = "/api/iot/ingest/"

    def test_ingest_creates_appareildata_and_updates_last_seen(self):
        payload = {
            "device_id": "TEST_ESP32",
            "data": {"temperature": 25.1, "humidity": 55}
        }
        resp = self.client.post(self.url, payload, format="json")
        self.assertIn(resp.status_code, (200, 201), msg=f"Status: {resp.status_code} Body: {resp.content}")
        device = Device.objects.filter(device_id="TEST_ESP32").first()
        self.assertIsNotNone(device, "Device non créé")
        self.assertIsNotNone(device.last_seen, "Device.last_seen non mis à jour")
        appdata = AppareilData.objects.filter(device=device)
        self.assertTrue(appdata.exists(), "AppareilData non créé")
        self.assertTrue(ActionLog.objects.exists(), "Aucun ActionLog trouvé")


class DeviceQuotaIngestTest(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="quota-ingest-user", password="pass")
        Token.objects.filter(user=self.user).delete()
        self.token = Token.objects.create(user=self.user, key="quotaingesttoken123")
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION="Token " + self.token.key)
        self.url = "/api/iot/ingest/"
        # Plan free (par défaut, sans Subscription) = 1 appareil max.
        self.existing_device = Device.objects.create(user=self.user, device_id="DEV_EXISTING", name="Existant")

    def test_existing_device_can_still_send_data_at_quota(self):
        resp = self.client.post(
            self.url,
            {"device_id": "DEV_EXISTING", "data": {"temperature": 21}},
            format="json",
        )
        self.assertIn(resp.status_code, (200, 201), msg=resp.content)

    def test_new_device_blocked_once_quota_reached(self):
        resp = self.client.post(
            self.url,
            {"device_id": "DEV_NEW", "data": {"temperature": 21}},
            format="json",
        )
        self.assertEqual(resp.status_code, 403, msg=resp.content)
        self.assertFalse(Device.objects.filter(device_id="DEV_NEW").exists())

    def test_superuser_bypasses_device_quota(self):
        self.user.is_superuser = True
        self.user.save()
        resp = self.client.post(
            self.url,
            {"device_id": "DEV_NEW_SUPERUSER", "data": {"temperature": 21}},
            format="json",
        )
        self.assertIn(resp.status_code, (200, 201), msg=resp.content)


class ExportAirDataPlanGateTest(TestCase):
    def setUp(self):
        from monetisation.models import Subscription
        User = get_user_model()
        self.user = User.objects.create_user(username="export-user", password="pass")
        self.subscription, _ = Subscription.objects.get_or_create(user=self.user, defaults={"plan": "free"})
        self.device = Device.objects.create(user=self.user, device_id="EXPORT_DEV", name="Capteur export")
        self.client = Client()
        self.client.force_login(self.user)
        self.url = f"/export/air-data/{self.device.id}/"

    def test_free_plan_cannot_export(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 403, msg=resp.content)

    def test_basic_plan_can_export(self):
        self.subscription.plan = "basic"
        self.subscription.save()
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            resp["Content-Type"],
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )


class DeviceLast10APITest(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="apiuser", password="pass")
        Token.objects.filter(user=self.user).delete()
        Token.objects.create(user=self.user, key="apitoken123")
        self.client = APIClient()
        Token.objects.filter(user=self.user).delete()
        Token.objects.create(user=self.user, key="apitoken123")
        self.client.credentials(HTTP_AUTHORIZATION="Token apitoken123")
        self.device = Device.objects.create(user=self.user, device_id="DEV_1", name="Dev1")

    def test_device_last10_returns_iso_and_is_anomaly(self):
        # create a sample AppareilData
        from django.utils import timezone
        ts = timezone.now()
        AppareilData.objects.create(device=self.device, payload={"temperature": 12}, received_at=ts, is_anomaly=False)

        url = f"/api/device/{self.device.id}/last10/"
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()["readings"]
        self.assertTrue(len(data) >= 1)
        self.assertIn('time', data[0])
        self.assertIn('pm25', data[0])
        self.assertEqual(data[0]['temperature'], 12)