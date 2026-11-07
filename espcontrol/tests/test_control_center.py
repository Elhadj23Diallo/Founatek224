from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from espcontrol.models import ActionLog, AppareilData, Device, Relais


User = get_user_model()


class DeviceCenterTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="device-owner", password="test-pass-123")
        self.other_user = User.objects.create_user(username="other-owner", password="test-pass-123")

    def test_device_center_is_scoped_to_user_and_reports_health(self):
        recent_device = Device.objects.create(
            user=self.user,
            device_id="sensor-recent",
            name="Station active",
            type="air_quality",
            last_seen=timezone.now(),
        )
        AppareilData.objects.create(
            device=recent_device,
            payload={"pm2p5": 8.4, "temperature": 23.1},
        )
        Device.objects.create(
            user=self.user,
            device_id="sensor-stale",
            name="Station silencieuse",
            last_seen=timezone.now() - timedelta(minutes=20),
        )
        Device.objects.create(
            user=self.other_user,
            device_id="private-device",
            name="Appareil privé",
            last_seen=timezone.now(),
        )
        self.client.force_login(self.user)

        response = self.client.get(reverse("device_center"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Station active")
        self.assertContains(response, "Station silencieuse")
        self.assertContains(response, "pm2p5")
        self.assertNotContains(response, "Appareil privé")
        self.assertEqual(response.context["device_count"], 2)
        self.assertEqual(response.context["online_count"], 1)
        self.assertEqual(response.context["offline_count"], 1)

    def test_device_center_requires_login(self):
        response = self.client.get(reverse("device_center"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response.url)


class RelayControlSafetyTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="relay-owner", password="test-pass-123")
        self.other_user = User.objects.create_user(username="relay-other", password="test-pass-123")
        self.relay = Relais.objects.create(user=self.user, num=7, nom="Ventilateur", etat=False)
        self.other_relay = Relais.objects.create(user=self.other_user, num=8, nom="Privé", etat=False)
        self.client.force_login(self.user)
        self.api_client = APIClient()
        self.api_client.force_authenticate(user=self.user)

    def test_web_relay_toggle_rejects_get_without_changing_state(self):
        response = self.client.get(reverse("toggle_relais", args=[self.relay.num]))

        self.assertEqual(response.status_code, 405)
        self.relay.refresh_from_db()
        self.assertFalse(self.relay.etat)
        self.assertFalse(ActionLog.objects.filter(user=self.user, action="RELAY_STATE_REQUESTED").exists())

    def test_web_relay_toggle_requires_csrf_token(self):
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.user)

        response = csrf_client.post(reverse("toggle_relais", args=[self.relay.num]))

        self.assertEqual(response.status_code, 403)
        self.relay.refresh_from_db()
        self.assertFalse(self.relay.etat)

    def test_web_relay_toggle_records_requested_state_and_audit_log(self):
        response = self.client.post(reverse("toggle_relais", args=[self.relay.num]))

        self.assertEqual(response.status_code, 302)
        self.relay.refresh_from_db()
        self.assertTrue(self.relay.etat)
        log = ActionLog.objects.get(user=self.user, action="RELAY_STATE_REQUESTED")
        self.assertEqual(log.details["source"], "web")
        self.assertEqual(log.details["relay_num"], self.relay.num)
        self.assertEqual(log.details["previous_state"], "off")
        self.assertEqual(log.details["requested_state"], "on")
        history = self.client.get(reverse("afficher_relais"))
        self.assertContains(history, "Historique des demandes récentes")
        self.assertContains(history, "Ventilateur")
        self.assertContains(history, "ON")

    def test_web_user_cannot_toggle_another_users_relay(self):
        response = self.client.post(reverse("toggle_relais", args=[self.other_relay.num]))

        self.assertEqual(response.status_code, 404)
        self.other_relay.refresh_from_db()
        self.assertFalse(self.other_relay.etat)

    def test_mobile_relay_api_records_state_without_claiming_hardware_confirmation(self):
        response = self.api_client.post(
            reverse("mobile_relay_detail", args=[self.relay.num]),
            {"state": "on"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["state_recorded"])
        self.assertFalse(response.data["hardware_confirmed"])
        self.assertTrue(response.data["changed"])
        log = ActionLog.objects.get(user=self.user, action="RELAY_STATE_REQUESTED")
        self.assertEqual(log.details["source"], "mobile_api")

    def test_mobile_devices_returns_stored_device_type(self):
        device = Device.objects.create(
            user=self.user,
            device_id="my-air-sensor",
            name="Air sensor",
            type="air_quality",
            last_seen=timezone.now(),
        )
        AppareilData.objects.create(device=device, payload={"pm2p5": 12.0})

        response = self.api_client.get(reverse("mobile_devices"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        payload = next(item for item in response.data if item["device_id"] == "my-air-sensor")
        self.assertEqual(payload["type"], "air_quality")
        self.assertEqual(payload["reading_count"], 1)
        self.assertEqual(payload["latest"]["pm2p5"], 12.0)
        self.assertTrue(payload["is_online"])
