from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.utils import timezone

from espcontrol.chat_reports import build_daily_report
from espcontrol.models import ChatEscalation, ChatLog
from espcontrol.chatbot_model import Chatbot, ESCALATION_REPLY


class LoggingAndEscalationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("marie", "marie@test.com", "pw")

    def _groq_msg(self, content=None, tool_calls=None):
        return {"role": "assistant", "content": content, "tool_calls": tool_calls}

    @patch("espcontrol.chatbot_model.call_groq_chat")
    def test_ai_chat_escalates_and_returns_fixed_message(self, mock_groq):
        tool_call = {
            "id": "call_1",
            "function": {
                "name": "escalate_to_support",
                "arguments": '{"resume": "Demande de remboursement", "categorie": "facturation"}',
            },
        }
        mock_groq.return_value = self._groq_msg(tool_calls=[tool_call])

        bot = Chatbot(self.user)
        reply = bot.ai_chat("Je veux etre rembourse", channel="web")

        self.assertEqual(reply, ESCALATION_REPLY)
        self.assertTrue(bot.last_escalated)
        esc = ChatEscalation.objects.get(user=self.user)
        self.assertEqual(esc.category, "facturation")
        self.assertEqual(esc.channel, "web")
        self.assertEqual(esc.status, "nouveau")
        # Un seul aller-retour Groq : pas de deuxieme appel pour reformuler.
        mock_groq.assert_called_once()

    @patch("espcontrol.chatbot_model.call_groq_chat")
    def test_ai_chat_normal_answer_not_escalated(self, mock_groq):
        mock_groq.return_value = self._groq_msg(content="Voici votre reponse.")
        bot = Chatbot(self.user)
        reply = bot.ai_chat("Comment marche la boutique ?", channel="mobile")
        self.assertEqual(reply, "Voici votre reponse.")
        self.assertFalse(bot.last_escalated)
        self.assertEqual(ChatEscalation.objects.count(), 0)

    def test_chat_endpoint_logs_turn(self):
        self.client.force_login(self.user)
        with patch("espcontrol.chatbot_model.Chatbot.get_response", return_value="Salut !"):
            resp = self.client.post(
                "/chatbot/", data='{"message": "bonjour"}', content_type="application/json"
            )
        self.assertEqual(resp.status_code, 200)
        log = ChatLog.objects.get(user=self.user)
        self.assertEqual(log.channel, "web")
        self.assertEqual(log.message, "bonjour")
        self.assertEqual(log.response, "Salut !")
        self.assertFalse(log.escalated)

    def test_daily_report_groups_by_user_and_counts_escalations(self):
        ChatLog.objects.create(user=self.user, channel="web", message="q1", response="r1", escalated=False)
        ChatLog.objects.create(user=self.user, channel="mobile", message="q2", response="r2", escalated=True)
        ChatEscalation.objects.create(
            user=self.user, channel="mobile", category="technique",
            summary="Panne capteur", original_message="q2",
        )
        report = build_daily_report(timezone.localdate())
        self.assertEqual(report["total_messages"], 2)
        self.assertEqual(report["unique_users"], 1)
        self.assertEqual(report["web_count"], 1)
        self.assertEqual(report["mobile_count"], 1)
        self.assertEqual(report["escalation_count"], 1)
        self.assertEqual(report["conversations"][0]["count"], 2)
        self.assertEqual(report["conversations"][0]["escalations"], 1)

    def test_daily_report_page_staff_only(self):
        self.client.force_login(self.user)
        resp = self.client.get("/chatbot/rapport/")
        self.assertEqual(resp.status_code, 403)

        self.user.is_staff = True
        self.user.save()
        resp = self.client.get("/chatbot/rapport/")
        self.assertEqual(resp.status_code, 200)

    def test_resolve_escalation_marks_traite(self):
        staff = User.objects.create_user("admin", "a@a.com", "pw", is_staff=True)
        esc = ChatEscalation.objects.create(
            user=self.user, channel="web", category="autre",
            summary="test", original_message="test",
        )
        self.client.force_login(staff)
        resp = self.client.post(f"/chatbot/escalade/{esc.id}/resoudre/")
        self.assertEqual(resp.status_code, 200)
        esc.refresh_from_db()
        self.assertEqual(esc.status, "traite")
        self.assertEqual(esc.handled_by, staff)

    def test_mobile_chatbot_logs_turn(self):
        from rest_framework.authtoken.models import Token
        tok, _ = Token.objects.get_or_create(user=self.user)
        with patch("espcontrol.chatbot_model.Chatbot.get_response", return_value="Salut mobile !"):
            resp = self.client.post(
                "/api/mobile/chatbot/", data='{"message": "yo"}',
                content_type="application/json", HTTP_AUTHORIZATION=f"Token {tok.key}",
            )
        self.assertEqual(resp.status_code, 200)
        log = ChatLog.objects.get(user=self.user, channel="mobile")
        self.assertEqual(log.message, "yo")
        self.assertEqual(log.response, "Salut mobile !")


from unittest.mock import patch as _patch
from espcontrol.models import Relais, ChatPreference, ProactiveChatMessage


class NewToolsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("sekou", "sekou@test.com", "pw")

    def _msg(self, tool_calls=None, content=None):
        return {"role": "assistant", "content": content, "tool_calls": tool_calls}

    @patch("espcontrol.chatbot_model.call_groq_chat")
    def test_relais_tool_toggles_named_relais(self, mock_groq):
        Relais.objects.create(user=self.user, num=1, nom="Salon", etat=False)
        tc = {"id": "1", "function": {"name": "set_relais", "arguments": '{"identifiant": "salon", "etat": "on"}'}}
        mock_groq.side_effect = [self._msg(tool_calls=[tc]), self._msg(content="Salon allumé !")]
        bot = Chatbot(self.user)
        reply = bot.ai_chat("allume le salon stp", channel="web")
        self.assertEqual(reply, "Salon allumé !")
        r = Relais.objects.get(user=self.user, num=1)
        self.assertTrue(r.etat)

    @patch("espcontrol.chatbot_model.call_groq_chat")
    def test_relais_tool_unknown_name(self, mock_groq):
        tc = {"id": "1", "function": {"name": "set_relais", "arguments": '{"identifiant": "grenier", "etat": "on"}'}}
        mock_groq.side_effect = [self._msg(tool_calls=[tc]), self._msg(content="Je n'ai pas trouvé.")]
        bot = Chatbot(self.user)
        bot.ai_chat("allume le grenier", channel="web")
        sent_tool_result = mock_groq.call_args_list[1][0][0][-1]["content"]
        self.assertIn("introuvable", sent_tool_result)

    @patch("espcontrol.chatbot_model.call_groq_chat")
    def test_remember_preference_tool_persists_and_resurfaces(self, mock_groq):
        tc = {"id": "1", "function": {"name": "remember_preference", "arguments": '{"cle": "surnom", "valeur": "Chef"}'}}
        mock_groq.side_effect = [self._msg(tool_calls=[tc]), self._msg(content="Noté, Chef !")]
        bot = Chatbot(self.user)
        bot.ai_chat("retiens que tu dois m'appeler Chef", channel="web")
        self.assertEqual(ChatPreference.objects.get(user=self.user, key="surnom").value, "Chef")
        self.assertIn("surnom=Chef", bot.get_user_context())

    def test_course_rag_finds_relevant_lesson(self):
        from iot.models import Organisation, Parcours, Lecon, BlocPedagogique
        org = Organisation.objects.create(nom="Test Org")
        parcours = Parcours.objects.create(
            organisation=org, created_by=self.user, titre="Arduino débutant",
            description="x", niveau="Débutant", is_published=True,
        )
        lecon = Lecon.objects.create(parcours=parcours, titre="La loi d'Ohm", ordre=1,
                                      resume="Comprendre tension, courant et résistance")
        BlocPedagogique.objects.create(
            lecon=lecon, type="texte", ordre=1,
            contenu="La loi d'Ohm relie la tension U, le courant I et la résistance R : U = R x I.",
        )
        from espcontrol.course_rag import search_course_content
        results = search_course_content("comment fonctionne la loi d'ohm et la resistance ?")
        self.assertTrue(results)
        self.assertEqual(results[0]["lecon"], "La loi d'Ohm")

    def test_course_rag_no_match_returns_empty(self):
        from espcontrol.course_rag import search_course_content
        self.assertEqual(search_course_content("bonjour comment ça va"), [])

    def test_agent_alert_creates_proactive_message(self):
        from espcontrol.models import Device, AgentAlert
        device = Device.objects.create(user=self.user, name="Capteur", device_id="D1")
        AgentAlert.objects.create(user=self.user, device=device, sensor="pm2p5", value="80",
                                   level="CRITICAL", message="Pic de pollution détecté")
        self.assertEqual(ProactiveChatMessage.objects.filter(user=self.user, delivered=False).count(), 1)

    def test_web_proactive_endpoint_delivers_and_logs(self):
        from espcontrol.models import Device, AgentAlert
        device = Device.objects.create(user=self.user, name="Capteur", device_id="D1")
        AgentAlert.objects.create(user=self.user, device=device, sensor="pm2p5", value="80",
                                   level="CRITICAL", message="Pic de pollution détecté")
        self.client.force_login(self.user)
        resp = self.client.get("/chatbot/proactive/")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data["messages"]), 1)
        self.assertEqual(ProactiveChatMessage.objects.get().delivered, True)
        self.assertEqual(ChatLog.objects.filter(proactive=True).count(), 1)
        # Second call: nothing left to deliver
        resp2 = self.client.get("/chatbot/proactive/")
        self.assertEqual(resp2.json()["messages"], [])

    def test_web_feedback_endpoint(self):
        log = ChatLog.objects.create(user=self.user, channel="web", message="q", response="r")
        self.client.force_login(self.user)
        resp = self.client.post(f"/chatbot/feedback/{log.id}/", data='{"rating": "up"}', content_type="application/json")
        self.assertEqual(resp.status_code, 200)
        log.refresh_from_db()
        self.assertEqual(log.rating, "up")

    def test_mobile_feedback_endpoint(self):
        from rest_framework.authtoken.models import Token
        tok, _ = Token.objects.get_or_create(user=self.user)
        log = ChatLog.objects.create(user=self.user, channel="mobile", message="q", response="r")
        resp = self.client.post(
            f"/api/mobile/chatbot/feedback/{log.id}/", data='{"rating": "down"}',
            content_type="application/json", HTTP_AUTHORIZATION=f"Token {tok.key}",
        )
        self.assertEqual(resp.status_code, 200)
        log.refresh_from_db()
        self.assertEqual(log.rating, "down")

    def test_chatbot_response_includes_log_id(self):
        self.client.force_login(self.user)
        with _patch("espcontrol.chatbot_model.Chatbot.get_response", return_value="Salut !"):
            resp = self.client.post("/chatbot/", data='{"message": "bonjour"}', content_type="application/json")
        self.assertIsNotNone(resp.json()["log_id"])
