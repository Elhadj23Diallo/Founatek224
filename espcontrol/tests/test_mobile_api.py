from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from espcontrol.models import AgentAlert, AppareilData, Device, Relais


class MobileApiTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="mobuser", password="strongpass123")
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        Relais.objects.create(user=self.user, num=1, etat=True, nom="Lumière")

    def test_relay_list_api_returns_user_relays(self):
        url = reverse("mobile_relay_list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        payload = response.json()
        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]["num"], 1)
        self.assertEqual(payload[0]["etat"], "on")

    def test_air_quality_summary_api_returns_user_devices(self):
        device = Device.objects.create(user=self.user, device_id="dev-1", name="Capteur 1")
        AppareilData.objects.create(device=device, payload={"pm2p5": 12.5, "pm10": 20.0, "temperature": 24.0})

        url = reverse("mobile_air_quality_summary")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        payload = response.json()
        self.assertEqual(payload[0]["device"]["name"], "Capteur 1")
        self.assertEqual(payload[0]["latest"]["pm2p5"], 12.5)

    def test_alerts_api_returns_user_alerts(self):
        device = Device.objects.create(user=self.user, device_id="dev-2", name="Capteur 2")
        AgentAlert.objects.create(user=self.user, device=device, code="AQ-1", message="Pollution", level="WARN", sensor="pm2p5", value=48.0)

        url = reverse("mobile_alerts")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        payload = response.json()
        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]["message"], "Pollution")
