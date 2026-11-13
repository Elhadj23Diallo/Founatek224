from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from espcontrol.models import AgentAlert, AppareilData, Device, Relais
from monetisation.models import Referral


class MobileReferralApiTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="referral-user", password="strongpass123")
        token, _ = Token.objects.get_or_create(user=self.user)
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

    def test_referral_endpoint_does_not_crash_for_user_with_no_referrals_yet(self):
        # Chaque inscription crée déjà une ligne Referral(referred=user) — on la
        # simule ici comme le fait iot.views.register.
        own_referral = Referral.objects.create(referrer=None, referred=self.user, code="my-own-code")

        url = reverse("mobile_monetisation_referral")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        payload = response.json()
        self.assertEqual(payload["code"], own_referral.code)
        self.assertEqual(payload["referred_count"], 0)

    def test_referral_endpoint_counts_people_referred_by_user(self):
        Referral.objects.create(referrer=None, referred=self.user, code="my-own-code")
        friend = get_user_model().objects.create_user(username="referred-friend", password="x")
        Referral.objects.create(referrer=self.user, referred=friend, code="friend-code")

        response = self.client.get(reverse("mobile_monetisation_referral"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["referred_count"], 1)


class MobileApiTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="mobuser", password="strongpass123")
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        # APIKeyMiddleware checks the raw Authorization header before DRF's
        # own auth runs, so force_authenticate() alone isn't enough here.
        token, _ = Token.objects.get_or_create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
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
