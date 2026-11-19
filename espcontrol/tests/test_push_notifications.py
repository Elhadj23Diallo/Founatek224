"""Enregistrement du jeton push Expo et envoi de la notification quand une
AgentAlert est créée. Aucun appel réseau réel vers Expo : requests.post est mocké."""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from espcontrol.models import AgentAlert, PushToken

User = get_user_model()


class PushTokenRegistrationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="push-user", password="strongpass123")
        token, _ = Token.objects.get_or_create(user=self.user)
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

    def test_registers_a_new_token(self):
        response = self.client.post(
            reverse("mobile_register_push_token"), {"token": "ExponentPushToken[abc123]"}, format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(PushToken.objects.get().user, self.user)

    def test_missing_token_is_rejected(self):
        response = self.client.post(reverse("mobile_register_push_token"), {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(PushToken.objects.count(), 0)

    def test_same_device_token_reassigned_to_new_user(self):
        other_user = User.objects.create_user(username="push-user-2", password="strongpass123")
        PushToken.objects.create(user=other_user, token="ExponentPushToken[shared]")

        response = self.client.post(
            reverse("mobile_register_push_token"), {"token": "ExponentPushToken[shared]"}, format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(PushToken.objects.count(), 1)
        self.assertEqual(PushToken.objects.get().user, self.user)


@patch("espcontrol.signals.requests.post")
class AlertPushSignalTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="alert-user", password="strongpass123")

    def test_critical_alert_pushes_to_registered_tokens(self, mock_post):
        PushToken.objects.create(user=self.user, token="ExponentPushToken[device1]")
        AgentAlert.objects.create(user=self.user, code="X", level="CRITICAL", message="Test critique")

        mock_post.assert_called_once()
        sent = mock_post.call_args.kwargs["json"]
        self.assertEqual(len(sent), 1)
        self.assertEqual(sent[0]["to"], "ExponentPushToken[device1]")
        self.assertIn("Test critique", sent[0]["body"])

    def test_info_alert_does_not_push(self, mock_post):
        PushToken.objects.create(user=self.user, token="ExponentPushToken[device1]")
        AgentAlert.objects.create(user=self.user, code="X", level="INFO", message="Juste une info")

        mock_post.assert_not_called()

    def test_no_registered_device_does_not_push(self, mock_post):
        AgentAlert.objects.create(user=self.user, code="X", level="WARN", message="Attention")

        mock_post.assert_not_called()

    def test_push_failure_does_not_break_alert_creation(self, mock_post):
        mock_post.side_effect = Exception("réseau indisponible")
        PushToken.objects.create(user=self.user, token="ExponentPushToken[device1]")

        alert = AgentAlert.objects.create(user=self.user, code="X", level="WARN", message="Attention")

        self.assertIsNotNone(alert.pk)
