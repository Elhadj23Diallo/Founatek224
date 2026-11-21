"""Protection CSRF : un navigateur doit envoyer le jeton, un appareil (jeton d'API) non."""
import json

from django.contrib.auth import get_user_model
from django.middleware.csrf import _get_new_csrf_string
from django.test import Client, TestCase
from rest_framework.authtoken.models import Token

from espcontrol.models import Relais

User = get_user_model()


class CsrfProtectionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("csrf-user", password="pass-1234")
        self.relay = Relais.objects.create(num=1, user=self.user, nom="Lampe")
        self.token, _ = Token.objects.get_or_create(user=self.user)
        self.browser = Client(enforce_csrf_checks=True)

    def post_json(self, client, url, data, **extra):
        return client.post(url, data=json.dumps(data), content_type="application/json", **extra)

    def with_csrf(self, client):
        secret = _get_new_csrf_string()
        client.cookies["csrftoken"] = secret
        return {"HTTP_X_CSRFTOKEN": secret}

    # --- relais : appelés par le site (session) et par les ESP32 (jeton d'API) ---
    def test_browser_without_csrf_cannot_switch_relay(self):
        self.browser.force_login(self.user)
        response = self.post_json(self.browser, "/api/relais/1/set/", {"state": "on"})
        self.assertEqual(response.status_code, 403)
        self.relay.refresh_from_db()
        self.assertFalse(self.relay.etat)

    def test_browser_with_csrf_switches_relay(self):
        self.browser.force_login(self.user)
        response = self.post_json(self.browser, "/api/relais/1/set/", {"state": "on"}, **self.with_csrf(self.browser))
        self.assertEqual(response.status_code, 200)
        self.relay.refresh_from_db()
        self.assertTrue(self.relay.etat)

    def test_device_with_api_token_needs_no_csrf(self):
        device = Client(enforce_csrf_checks=True)
        response = self.post_json(device, "/api/relais/1/set/", {"state": "on"},
                                  HTTP_AUTHORIZATION=f"Token {self.token.key}")
        self.assertEqual(response.status_code, 200)
        self.relay.refresh_from_db()
        self.assertTrue(self.relay.etat)

    # --- vues réservées au site ---
    def test_mark_alert_read_requires_login(self):
        response = Client().post("/alert/read/1/")
        self.assertEqual(response.status_code, 302)

    def test_mark_alert_read_requires_csrf(self):
        self.browser.force_login(self.user)
        self.assertEqual(self.browser.post("/alert/read/1/").status_code, 403)

    def test_live_status_requires_csrf(self):
        self.browser.force_login(self.user)
        response = self.post_json(self.browser, "/techfeed/live/update/", {"status": "stop"})
        self.assertEqual(response.status_code, 403)

    def test_live_status_rejects_invalid_json(self):
        client = Client()
        client.force_login(self.user)
        response = client.post("/techfeed/live/update/", data="pas du json", content_type="application/json")
        self.assertEqual(response.status_code, 400)

    def test_quiz_reset_requires_csrf(self):
        self.browser.force_login(self.user)
        self.assertEqual(self.browser.post("/reset-quiz/").status_code, 403)

    def test_quiz_answers_reject_invalid_json_and_attempt(self):
        client = Client()
        client.force_login(self.user)
        self.assertEqual(client.post("/save-answers/", data="{", content_type="application/json").status_code, 400)
        response = self.post_json(client, "/save-answers/", {"attempt": "abc", "answers": {}})
        self.assertEqual(response.status_code, 400)
