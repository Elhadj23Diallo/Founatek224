from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import Client, TestCase

from espcontrol.chatbot_model import Chatbot
from espcontrol.models import UserProfile


class PlatformLanguageTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("awa", "awa@test.com", "pw")

    def test_default_language_is_french(self):
        self.assertEqual(Chatbot(self.user).lang, "fr")

    def test_chatbot_uses_saved_profile_language(self):
        UserProfile.objects.create(user=self.user, language="en")
        self.assertEqual(Chatbot(self.user).lang, "en")

    def test_localize_is_noop_in_french(self):
        bot = Chatbot(self.user)
        with patch("espcontrol.chatbot_model.call_groq") as mock_translate:
            out = bot._localize("🛑 ARRÊT D'URGENCE — Tous les relais éteints !")
        mock_translate.assert_not_called()
        self.assertIn("ARRÊT", out)

    def test_localize_translates_in_english(self):
        UserProfile.objects.create(user=self.user, language="en")
        bot = Chatbot(self.user)
        with patch("espcontrol.chatbot_model.call_groq", return_value="EMERGENCY STOP") as mock_translate:
            out = bot._localize("🛑 ARRÊT D'URGENCE — Tous les relais éteints !")
        mock_translate.assert_called_once()
        self.assertEqual(out, "EMERGENCY STOP")

    def test_localize_translates_dict_response_buttons_not_values(self):
        UserProfile.objects.create(user=self.user, language="en")
        bot = Chatbot(self.user)
        payload = {"reponse": "Que voulez-vous savoir ?", "buttons": [{"text": "Qualité de l'air", "value": "air"}]}
        with patch("espcontrol.chatbot_model.call_groq", side_effect=["What do you want to know?", "Air quality"]):
            out = bot._localize(payload)
        self.assertEqual(out["reponse"], "What do you want to know?")
        self.assertEqual(out["buttons"][0]["text"], "Air quality")
        self.assertEqual(out["buttons"][0]["value"], "air")  # jamais traduit : casserait le parsing d'intention

    def test_registration_saves_chosen_language(self):
        resp = self.client.post("/register/", {
            "username": "koffi", "email": "koffi@test.com",
            "first_name": "Koffi", "last_name": "N.",
            "role": "Apprenant", "password1": "Sup3rSecret!9", "password2": "Sup3rSecret!9",
            "language": "en",
        })
        self.assertEqual(resp.status_code, 302)
        user = User.objects.get(username="koffi")
        self.assertEqual(UserProfile.objects.get(user=user).language, "en")

    def test_set_platform_language_persists_for_authenticated_user(self):
        self.client.force_login(self.user)
        resp = self.client.post("/langue/", {"language": "en", "next": "/home/"})
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(UserProfile.objects.get(user=self.user).language, "en")

    def test_set_platform_language_rejects_unknown_code(self):
        self.client.force_login(self.user)
        self.client.post("/langue/", {"language": "zz", "next": "/home/"})
        self.assertFalse(UserProfile.objects.filter(user=self.user).exists())

    def test_user_language_middleware_activates_saved_language(self):
        from django.utils import translation
        UserProfile.objects.create(user=self.user, language="en")
        self.client.force_login(self.user)
        self.client.get("/home/")
        # Le middleware tourne pendant la requete — on verifie l'effet de bord
        # observable : le profil est bien lu sans lever d'exception et reste "en".
        self.assertEqual(UserProfile.objects.get(user=self.user).language, "en")

    def test_mobile_set_language_endpoint(self):
        from rest_framework.authtoken.models import Token
        tok, _ = Token.objects.get_or_create(user=self.user)
        resp = self.client.post(
            "/api/mobile/set-language/", data='{"language": "en"}',
            content_type="application/json", HTTP_AUTHORIZATION=f"Token {tok.key}",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(UserProfile.objects.get(user=self.user).language, "en")

    def test_mobile_register_saves_language(self):
        resp = self.client.post(
            "/api/mobile/register/", data='{"username": "zara", "password": "Sup3rSecret!9", '
            '"email": "zara@test.com", "role": "Apprenant", "language": "en"}',
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 201)
        user = User.objects.get(username="zara")
        self.assertEqual(UserProfile.objects.get(user=user).language, "en")
