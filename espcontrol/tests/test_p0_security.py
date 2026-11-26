from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal
from threading import Barrier
from unittest.mock import patch

from django.contrib.admin import AdminSite
from django.contrib.auth import get_user_model
from django.db import connections
from django.test import TestCase, TransactionTestCase, override_settings
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from espcontrol.admin import ActionLogAdmin
from espcontrol.chatbot_model import Chatbot
from espcontrol.course_rag import search_course_content
from espcontrol.models import AccessLog, AccessRule, ActionLog, AppareilData, Badge, Door
from iot.models import BlocPedagogique, Lecon, Organisation, Parcours, ParcoursAccess, Progression, Quiz
from monetisation.models import PaymentRequest, Transaction, Wallet
from product_transparency.models import Company, Product, ProductPricing, Sale

User = get_user_model()
UPGRADE = "/api/mobile/monetisation/upgrade/"


def api_for(token, compatible=True):
    client = APIClient()
    headers = {
        "HTTP_X_FOUNATEK_PLATFORM": "android",
        "HTTP_X_FOUNATEK_BUILD": "100",
        "HTTP_X_FOUNATEK_CONTRACT": "2",
    } if compatible else {}
    client.credentials(HTTP_AUTHORIZATION=f"Token {token}", **headers)
    return client


class SecurityRegressionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("security-owner")
        self.other = User.objects.create_user("security-other")
        self.token, _ = Token.objects.get_or_create(user=self.user)
        self.api = api_for(self.token.key)

    @patch("espcontrol.agent.agent.FounatekAgent.run")
    def test_ingestion_and_legacy_log_are_safe(self, run):
        payload = {"temperature": 22, "untrusted": "fixture-secret"}
        response = self.api.post("/api/iot/ingest/", {"device_id": "fixture", "data": payload}, format="json")
        self.assertEqual(response.status_code, 201, response.content)
        self.assertTrue(AppareilData.objects.filter(device__user=self.user).exists())
        log = ActionLog.objects.filter(user=self.user, action="ingest").latest("id")
        self.assertEqual(set(log.details), {"device_pk", "event"})
        historical = ActionLog.objects.create(user=self.user, action="ingest",
            details={"token_key": self.token.key, "payload": {"reading": "fixture-secret"}})
        response = self.api.get("/api/mobile/action-logs/")
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, self.token.key)
        self.assertNotContains(response, "fixture-secret")
        historical.refresh_from_db()
        self.assertEqual(historical.details["token_key"], self.token.key)
        admin = ActionLogAdmin(ActionLog, AdminSite())
        self.assertEqual(admin.safe_details(historical), {"event": "sensor_data_received"})

    def test_both_rfid_routes_deny_foreign_door_before_creating_log(self):
        door = Door.objects.create(name="Fixture door", slug="fixture-door", owner=self.other)
        for route in ("/api/check_access/", "/api/mobile/access-check/"):
            with self.subTest(route=route):
                response = self.api.post(route, {"door": door.slug, "uid": "fixture-badge"}, format="multipart")
                self.assertEqual(response.status_code, 403)
                self.assertEqual(response.json()["action"], "deny")
                self.assertNotIn("owner", response.json())
                self.assertFalse(AccessLog.objects.filter(door=door).exists())

    def test_rfid_staff_requires_door_ownership_and_owner_keeps_firmware_access(self):
        staff = User.objects.create_user("security-staff", is_staff=True)
        staff_token, _ = Token.objects.get_or_create(user=staff)
        door = Door.objects.create(name="Test door", slug="owned-fixture", owner=self.user)
        badge = Badge.objects.create(uid="fixture-tag", owner=self.user)
        AccessRule.objects.create(badge=badge, door=door, allowed=True)
        payload = {"door": door.slug, "uid": badge.uid}
        for route in ("/api/check_access/", "/api/mobile/access-check/"):
            with self.subTest(route=route):
                self.assertEqual(api_for(staff_token.key).post(route, payload).status_code, 403)
                response = self.api.post(route, payload)
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.json()["allowed"])

    @patch("espcontrol.views._read_live_frame", return_value=b"fake-jpeg")
    def test_mjpeg_returns_a_multipart_frame_and_can_be_closed(self, read_frame):
        route = "/api/mobile/surveillance/stream/fixture/"
        response = APIClient().get(route, {"token": self.token.key})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["Content-Type"], "multipart/x-mixed-replace; boundary=frame")
        self.assertIn("no-store", response.headers["Cache-Control"])
        try:
            self.assertEqual(next(iter(response.streaming_content)),
                b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: 9\r\n\r\nfake-jpeg\r\n")
        finally:
            with patch("django.http.response.signals.request_finished.send"):
                response.close()
        read_frame.assert_called_with(self.user.pk, "fixture")

    @patch("espcontrol.views._frame_id", return_value=1)
    @patch("espcontrol.views._read_live_frame")
    def test_camera_query_credential_is_active_and_scoped(self, read_frame, frame_id):
        read_frame.side_effect = lambda owner, camera: b"fixture-frame" if owner == self.user.pk else None
        route = "/api/mobile/surveillance/snapshot/fixture/"
        self.assertEqual(APIClient().get(route, {"token": self.token.key}).status_code, 200)
        other_token, _ = Token.objects.get_or_create(user=self.other)
        self.assertEqual(APIClient().get(route, {"token": other_token.key}).status_code, 404)
        self.assertEqual(APIClient().get("/api/mobile/action-logs/", {"token": self.token.key}).status_code, 403)
        cameras = "/api/mobile/surveillance/cameras/"
        self.assertEqual(APIClient().get(cameras, {"token": self.token.key}).status_code, 403)
        self.assertEqual(self.api.get(cameras).status_code, 200)
        self.user.is_active = False
        self.user.save(update_fields=["is_active"])
        read_frame.reset_mock()
        self.assertEqual(APIClient().get(route, {"token": self.token.key}).status_code, 403)
        read_frame.assert_not_called()

    def lessons(self):
        org = Organisation.objects.create(nom="Fixture academy", type="Universite")
        parcours = Parcours.objects.create(organisation=org, created_by=self.other,
            titre="Fixture course", niveau="Debutant", is_published=True, prix=Decimal("10"))
        first = Lecon.objects.create(parcours=parcours, titre="Intro", ordre=1)
        second = Lecon.objects.create(parcours=parcours, titre="Albatross", resume="Albatross resume", ordre=2)
        BlocPedagogique.objects.create(lecon=second, type="texte", contenu="Albatross block")
        return parcours, first, second

    def test_rag_requires_entitlement_and_unlocked_lesson(self):
        parcours, first, _ = self.lessons()
        self.assertEqual(search_course_content("albatross", user=self.user), [])
        access = ParcoursAccess.objects.create(user=self.user, parcours=parcours, provider="stripe", active=True)
        self.assertEqual(search_course_content("albatross", user=self.user), [])
        Progression.objects.create(user=self.user, lecon=first, completed=True, score=100)
        self.assertTrue(search_course_content("albatross", user=self.user))
        access.active = False
        access.save(update_fields=["active"])
        self.assertEqual(search_course_content("albatross", user=self.user), [])

    @patch("espcontrol.chatbot_model.call_groq_chat", return_value={"content": "fixture"})
    def test_nexus_prompt_excludes_locked_course(self, groq):
        parcours, _, _ = self.lessons()
        ParcoursAccess.objects.create(user=self.user, parcours=parcours, provider="stripe", active=True)
        Chatbot(self.user).ai_chat("albatross")
        system_message = groq.call_args.args[0][0]["content"]
        self.assertNotIn("Albatross block", system_message)
        self.assertNotIn("Albatross resume", system_message)

    def test_progression_uses_server_fields_and_keeps_original_lesson(self):
        parcours, first, second = self.lessons()
        ParcoursAccess.objects.create(user=self.user, parcours=parcours, provider="stripe", active=True)
        resp = self.api.post("/api/progression/", {"lecon": first.pk, "completed": True, "score": 100}, format="json")
        self.assertEqual(resp.status_code, 201, resp.content)
        progress = Progression.objects.get(user=self.user, lecon=first)
        self.assertFalse(progress.completed)
        self.assertEqual(progress.score, 0)
        route = f"/api/progression/{progress.pk}/"
        self.assertEqual(self.api.patch(route, {"lecon": second.pk}, format="json").status_code, 403)
        self.assertEqual(self.api.patch(route, {"completed": True, "score": 100}, format="json").status_code, 200)
        progress.refresh_from_db()
        self.assertEqual((progress.lecon_id, progress.completed, progress.score), (first.pk, False, 0))

    def test_quiz_hides_answers_before_submission_and_grades_on_server(self):
        parcours, first, second = self.lessons()
        ParcoursAccess.objects.create(user=self.user, parcours=parcours, provider="stripe", active=True)
        question = Quiz.objects.create(lecon=first, question="Fixture?", choix_a="One", choix_b="Two",
            bonne_reponse="A", explication="Fixture explanation")
        lesson = self.api.get(f"/api/lecons/{first.pk}/")
        self.assertEqual(lesson.status_code, 200)
        quiz = lesson.json()["quizzes"][0]
        self.assertNotIn("bonne_reponse", quiz)
        self.assertNotIn("explication", quiz)
        self.assertIn("plusieurs_reponses", quiz)
        legacy = api_for(self.token.key, compatible=False).get(f"/api/lecons/{first.pk}/")
        self.assertEqual(legacy.status_code, 409)
        self.assertEqual(legacy.json()["code"], "update_required")
        browser = APIClient()
        browser.force_login(self.user)
        browser_lesson = browser.get(f"/api/lecons/{first.pk}/")
        self.assertEqual(browser_lesson.status_code, 200)
        self.assertNotIn("bonne_reponse", browser_lesson.json()["quizzes"][0])
        self.assertEqual(api_for(self.token.key, compatible=False).get("/api/lecons/").status_code, 200)
        locked = self.api.post(f"/api/mobile/education/lecons/{second.pk}/submit/", {"answers": {}}, format="json")
        self.assertEqual(locked.status_code, 403)
        self.assertFalse(Progression.objects.filter(user=self.user, lecon=second).exists())
        empty = self.api.post(f"/api/mobile/education/lecons/{first.pk}/submit/", {"answers": {}}, format="json")
        self.assertEqual(empty.status_code, 400)
        self.assertNotIn("details", empty.json())
        self.assertFalse(Progression.objects.filter(user=self.user, lecon=first).exists())
        result = self.api.post(f"/api/mobile/education/lecons/{first.pk}/submit/", {
            "answers": {str(question.pk): "A"}, "score": 0, "completed": False,
        }, format="json")
        self.assertEqual(result.status_code, 200, result.content)
        self.assertEqual((result.json()["score"], result.json()["completed"]), (100, True))
        self.assertTrue(Progression.objects.get(user=self.user, lecon=first).completed)
        no_quiz = api_for(self.token.key, compatible=False).get(f"/api/lecons/{second.pk}/")
        self.assertEqual(no_quiz.status_code, 200)
        self.assertEqual(no_quiz.json()["quizzes"], [])

    def test_multiple_choice_quiz_does_not_disclose_answers_from_other_accounts(self):
        parcours, first, _ = self.lessons()
        ParcoursAccess.objects.create(user=self.user, parcours=parcours, provider="stripe", active=True)
        question = Quiz.objects.create(
            lecon=first, question="Choose two", choix_a="One", choix_b="Two", choix_c="Three",
            bonne_reponse="A,C", explication="Fixture explanation",
        )
        route = f"/api/mobile/education/lecons/{first.pk}/submit/"
        payload = {"answers": {str(question.pk): ["C", "A"]}}
        unentitled = User.objects.create_user("unentitled-learner")
        other_token, _ = Token.objects.get_or_create(user=unentitled)
        denied = api_for(other_token.key).post(route, payload, format="json")
        self.assertEqual(denied.status_code, 402)
        self.assertNotIn("details", denied.json())
        self.assertFalse(Progression.objects.filter(user=unentitled, lecon=first).exists())

        graded = self.api.post(route, payload, format="json")
        self.assertEqual(graded.status_code, 200, graded.content)
        self.assertEqual(graded.json()["score"], 100)
        self.assertIs(graded.json()["completed"], True)

    def test_sale_failure_restores_stock_on_web_and_mobile(self):
        company = Company.objects.create(user=self.user, name="Fixture shop", slug="fixture-shop")
        products = Product.objects.bulk_create([
            Product(company=company, name="First", sku="test-first", stock=3),
            Product(company=company, name="Second", sku="test-second", stock=1),
        ])
        for product in products:
            ProductPricing.objects.create(product=product, price=Decimal("2.50"),
                production_date=date(2026, 1, 1), expiry_date=date(2027, 1, 1))
        for route, product_ref in (
            ("/product_transparency/api/sales/", lambda p: str(p.uuid)),
            ("/api/mobile/transparence/sales/create/", lambda p: p.pk),
        ):
            for invalid_quantity in (0, -1, 2):
                with self.subTest(route=route, quantity=invalid_quantity):
                    items = [{"product_id": product_ref(products[0]), "quantity": 1},
                             {"product_id": product_ref(products[1]), "quantity": invalid_quantity}]
                    self.assertEqual(self.api.post(route, {"items": items}, format="json").status_code, 400)
                    self.assertFalse(Sale.objects.filter(company=company).exists())
                    products[0].refresh_from_db()
                    self.assertEqual(products[0].stock, 3)


class WalletConcurrencyTests(TransactionTestCase):
    def test_identical_concurrent_requests_debit_once_and_can_be_replayed(self):
        user = User.objects.create_user("wallet-concurrency")
        token, _ = Token.objects.get_or_create(user=user)
        Wallet.objects.filter(user=user).update(balance=Decimal("12"))
        barrier = Barrier(2)

        def submit():
            try:
                client = api_for(token.key)
                barrier.wait(timeout=10)
                return client.post(UPGRADE, {"plan": "basic"}, format="json", HTTP_IDEMPOTENCY_KEY="same-operation")
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = [pool.submit(submit) for _ in range(2)]
            statuses = [r.result(timeout=30).status_code for r in responses]
        self.assertIn(200, statuses)
        self.assertTrue(all(s in (200, 409) for s in statuses), statuses)
        replay = api_for(token.key).post(UPGRADE, {"plan": "basic"}, format="json", HTTP_IDEMPOTENCY_KEY="same-operation")
        self.assertEqual(replay.status_code, 200)
        self.assertTrue(replay.json()["replayed"])
        self.assertEqual(Wallet.objects.get(user=user).balance, Decimal("9"))
        self.assertEqual(Transaction.objects.filter(user=user, type="debit").count(), 1)
        self.assertEqual(PaymentRequest.objects.filter(user=user, purpose="subscription").count(), 1)


class MobileCompatibilityTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("compat-owner")
        self.other = User.objects.create_user("compat-other")
        self.token, _ = Token.objects.get_or_create(user=self.user)
        self.other_token, _ = Token.objects.get_or_create(user=self.other)
        self.api = api_for(self.token.key)

    def test_wallet_rejects_unkeyed_legacy_payment_without_debit(self):
        Wallet.objects.filter(user=self.user).update(balance=Decimal("12"))
        response = self.api.post(UPGRADE, {"plan": "basic"}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Wallet.objects.get(user=self.user).balance, Decimal("12"))
        self.assertFalse(Transaction.objects.filter(user=self.user, type="debit").exists())
        self.assertFalse(PaymentRequest.objects.filter(user=self.user, purpose="subscription").exists())
        self.assertEqual(self.api.post(UPGRADE, {"plan": "free"}, format="json").status_code, 200)

    @override_settings(MOBILE_MINIMUM_BUILDS={"android": 12, "ios": 20})
    def test_public_policy_uses_platform_build_and_contract(self):
        for platform, build, contract, expected in (
            ("android", "12", "2", True), ("ios", "19", "2", False),
            ("ios", "20", "2", True), ("android", "99", "1", False),
            ("web", "99", "2", False), ("android", "12.0", "2", False),
        ):
            with self.subTest(platform=platform, build=build, contract=contract):
                response = APIClient().get("/api/mobile/compatibility/",
                    HTTP_X_FOUNATEK_PLATFORM=platform, HTTP_X_FOUNATEK_BUILD=build,
                    HTTP_X_FOUNATEK_CONTRACT=contract)
                self.assertEqual(response.status_code, 200)
                self.assertIs(response.json()["compatible"], expected)
                self.assertEqual(response.json()["minimum_builds"], {"android": 12, "ios": 20})
                self.assertIn("no-store", response.headers["Cache-Control"])

    @override_settings(MOBILE_MINIMUM_BUILDS={"android": 12, "ios": 20})
    def test_wallet_blocks_legacy_and_too_old_build_even_with_key_before_any_write(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        for headers in ({}, {"HTTP_X_FOUNATEK_PLATFORM": "ios",
                            "HTTP_X_FOUNATEK_BUILD": "19", "HTTP_X_FOUNATEK_CONTRACT": "2"}):
            client = api_for(self.token.key, compatible=False)
            with self.subTest(headers=headers), CaptureQueriesContext(connection) as queries:
                response = client.post(UPGRADE, {"plan": "basic"}, format="json",
                                       HTTP_IDEMPOTENCY_KEY="fixture-operation", **headers)
                self.assertEqual(response.status_code, 409)
                self.assertEqual(response.json()["code"], "update_required")
            self.assertFalse(any(query["sql"].lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE"))
                                 for query in queries))

    def test_wallet_same_key_is_scoped_to_account_and_replay_debits_once(self):
        for user in (self.user, self.other):
            Wallet.objects.filter(user=user).update(balance=Decimal("12"))
        for client in (self.api, api_for(self.other_token.key)):
            initial = client.post(UPGRADE, {"plan": "basic"}, format="json", HTTP_IDEMPOTENCY_KEY="fixture-operation")
            self.assertEqual(initial.status_code, 200, initial.content)
            self.assertFalse(initial.json().get("replayed", False))
            replay = client.post(UPGRADE, {"plan": "basic"}, format="json", HTTP_IDEMPOTENCY_KEY="fixture-operation")
            self.assertEqual(replay.status_code, 200, replay.content)
            self.assertIs(replay.json()["replayed"], True)
            duplicate = client.post(UPGRADE, {"plan": "basic"}, format="json", HTTP_IDEMPOTENCY_KEY="different-key")
            self.assertEqual(duplicate.status_code, 409)
            self.assertEqual(duplicate.json()["code"], "plan_already_active")
        for user in (self.user, self.other):
            self.assertEqual(Wallet.objects.get(user=user).balance, Decimal("9"))
            self.assertEqual(Transaction.objects.filter(user=user, type="debit").count(), 1)
            self.assertEqual(PaymentRequest.objects.filter(user=user, purpose="subscription").count(), 1)

    def test_camera_snapshot_is_private_with_shared_camera_ids(self):
        from django.core.cache import caches

        cache = caches["live_frames"]
        for user, image in ((self.user, b"owner-frame"), (self.other, b"other-frame")):
            key = f"live_{user.pk}_shared-camera"
            cache.set(key, image)
            self.addCleanup(cache.delete, key)

        route = "/api/mobile/surveillance/snapshot/shared-camera/"
        for token, expected in ((self.token, b"owner-frame"), (self.other_token, b"other-frame")):
            with self.subTest(user=token.user_id):
                response = APIClient().get(route, {"token": token.key})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.content, expected)
                self.assertIn("no-store", response.headers["Cache-Control"])
                self.assertIn("private", response.headers["Cache-Control"])

    def test_legacy_ownerless_rfid_door_with_existing_rule_is_denied(self):
        door = Door.objects.create(name="Legacy door", slug="legacy-door")
        badge = Badge.objects.create(uid="legacy-fixture", owner=self.user)
        AccessRule.objects.create(badge=badge, door=door, allowed=True)
        for route in ("/api/check_access/", "/api/mobile/access-check/"):
            with self.subTest(route=route):
                response = self.api.post(route, {"door": door.slug, "uid": badge.uid})
                self.assertEqual(response.status_code, 403)
                self.assertEqual(response.json()["action"], "deny")
                self.assertFalse(AccessLog.objects.filter(door=door).exists())
