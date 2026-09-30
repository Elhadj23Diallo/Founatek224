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
