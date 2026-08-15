# ...existing code...
from django.test import TestCase
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
        data = resp.json()
        self.assertTrue(len(data) >= 1)
        self.assertIn('received_at', data[0])
        # received_at should be ISO-like (contain 'T')
        self.assertIn('T', data[0]['received_at'])
        self.assertIn('is_anomaly', data[0])