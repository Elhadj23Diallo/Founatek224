import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event
from time import monotonic, sleep
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.db import connection, connections
from django.test import TransactionTestCase, override_settings
from django.test.utils import CaptureQueriesContext
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from monetisation import wallet_control
from monetisation.models import PaymentRequest, Transaction, Wallet


class WalletControlTests(TransactionTestCase):
    def setUp(self):
        directory = self.enterContext(TemporaryDirectory())
        self.directory = Path(directory)
        self.enterContext(patch.dict(os.environ, {"FOUNATEK_WALLET_CONTROL_DIR": directory}))
        self.user = get_user_model().objects.create_user("wallet-pause-fixture")
        token, _ = Token.objects.get_or_create(user=self.user)
        self.token = token.key
        Wallet.objects.filter(user=self.user).update(balance=Decimal("12"))
        self.web = self.client
        self.web.force_login(self.user)

    def mobile(self, plan="basic", key="fixture-operation"):
        return self.api().post("/api/mobile/monetisation/upgrade/", {"plan": plan}, format="json",
                               HTTP_IDEMPOTENCY_KEY=key)

    def api(self):
        client = APIClient()
        client.credentials(
            HTTP_AUTHORIZATION=f"Token {self.token}",
            HTTP_X_FOUNATEK_PLATFORM="android",
            HTTP_X_FOUNATEK_BUILD="100",
            HTTP_X_FOUNATEK_CONTRACT="2",
        )
        return client

    def web_wallet(self):
        return self.web.post("/monetisation/abonnement/", {"provider": "wallet", "plan": "basic"})

    def assert_paused(self, response):
        self.assertEqual(response.status_code, 503, response.content)
        self.assertEqual(response.json()["code"], "wallet_paused")
        self.assertIn("no-store", response.headers["Cache-Control"])

    def assert_balance(self, balance, debits):
        self.assertEqual(Wallet.objects.get(user=self.user).balance, Decimal(balance))
        self.assertEqual(Transaction.objects.filter(user=self.user, type="debit").count(), debits)
        self.assertEqual(PaymentRequest.objects.filter(user=self.user, provider="wallet").count(), debits)

    def open_control(self):
        self.assertEqual(wallet_control.control("pause"), "paused-drained")
        with patch.object(wallet_control, "CAN_SPEND_ON_THIS_RELEASE", True):
            self.assertEqual(wallet_control.control("resume"), "open")

    def test_both_routes_fail_closed_with_missing_or_invalid_state(self):
        self.assertEqual(wallet_control.control("status"), "closed-uninitialized")
        for state in (None, b"paused\n", b"invalid"):
            if state is not None:
                wallet_control.control("pause")
                wallet_control._set_state(self.directory, state)
            with self.subTest(state=state), CaptureQueriesContext(connection) as queries:
                self.assert_paused(self.mobile())
                self.assert_paused(self.web_wallet())
            writes = ("INSERT", "UPDATE", "DELETE", "REPLACE")
            self.assertFalse(any(query["sql"].lstrip().upper().startswith(writes) for query in queries))
        self.assert_balance("12", 0)
        self.assertEqual(self.mobile(plan="free").status_code, 200)

    def test_pause_persists_in_a_fresh_process(self):
        self.assertEqual(wallet_control.control("pause"), "paused-drained")
        output = subprocess.check_output([sys.executable, "-m", "monetisation.wallet_control", "status"],
                                         text=True, timeout=10)
        self.assertEqual(output.strip(), "paused-drained")

    def test_wallet_resume_and_replay_on_candidate_only(self):
        self.open_control()
        if not wallet_control.CAN_SPEND_ON_THIS_RELEASE:
            self.assertEqual(wallet_control.control("status"), "closed-release")
            with self.assertRaises(ValueError):
                wallet_control.control("resume")
            self.assert_paused(self.mobile())
            self.assert_paused(self.web_wallet())
            self.assert_balance("12", 0)
            return

        self.assertEqual(self.mobile().status_code, 200)
        wallet_control.control("pause")
        self.assert_paused(self.mobile())
        self.assert_paused(self.web_wallet())
        self.assert_balance("9", 1)
        self.assertEqual(wallet_control.control("resume"), "open")
        replay = self.mobile()
        self.assertEqual(replay.status_code, 200)
        self.assertTrue(replay.json()["replayed"])
        self.assertEqual(self.web_wallet().status_code, 409)
        self.assert_balance("9", 1)

    def test_resumed_web_purchase_is_not_debited_again_by_web_or_mobile(self):
        if not wallet_control.CAN_SPEND_ON_THIS_RELEASE:
            self.skipTest("La version de secours maintient le Wallet fermé.")
        wallet_control.control("pause")
        self.assert_paused(self.web_wallet())
        wallet_control.control("resume")
        self.assertEqual(self.web_wallet().status_code, 302)
        self.assertEqual(self.web_wallet().status_code, 409)
        self.assertEqual(self.mobile().status_code, 409)
        self.assert_balance("9", 1)

    def test_another_process_holding_operation_lock_prevents_drain(self):
        self.open_control()
        code = (
            "from monetisation.wallet_control import _lock, control_directory\n"
            "with _lock(control_directory() / 'operations.lock'):\n"
            "    print('locked', flush=True)\n"
            "    input()\n"
        )
        worker = subprocess.Popen([sys.executable, "-c", code], stdin=subprocess.PIPE,
                                  stdout=subprocess.PIPE, text=True)
        try:
            self.assertEqual(worker.stdout.readline().strip(), "locked")
            if wallet_control.CAN_SPEND_ON_THIS_RELEASE:
                self.assertEqual(self.mobile().json()["code"], "wallet_busy")
                self.assertEqual(self.web_wallet().json()["code"], "wallet_busy")
            with self.assertRaises(wallet_control.WalletLockBusy):
                wallet_control.control("pause", timeout=0.1)
            self.assertEqual(wallet_control.control("status"), "paused-draining")
            self.assert_paused(self.mobile())
            self.assert_paused(self.web_wallet())
        finally:
            worker.communicate("\n", timeout=10)
        self.assertEqual(worker.returncode, 0)
        self.assertEqual(wallet_control.control("status"), "paused-drained")
        self.assert_balance("12", 0)

    def test_pause_waits_for_an_admitted_debit_then_rejects_replay(self):
        if not wallet_control.CAN_SPEND_ON_THIS_RELEASE:
            self.skipTest("La version de secours ne permet aucun débit Wallet.")
        self.open_control()
        debit_entered = Event()
        release_debit = Event()
        save = Wallet.save

        def delayed_save(wallet, *args, **kwargs):
            debit_entered.set()
            if not release_debit.wait(10):
                raise RuntimeError("Le test n'a pas libéré le débit.")
            return save(wallet, *args, **kwargs)

        def purchase():
            try:
                return self.mobile()
            finally:
                connections.close_all()

        with patch.object(Wallet, "save", delayed_save), ThreadPoolExecutor(max_workers=2) as pool:
            try:
                operation = pool.submit(purchase)
                self.assertTrue(debit_entered.wait(10))
                self.assertEqual(self.web_wallet().json()["code"], "wallet_busy")
                pause = pool.submit(wallet_control.control, "pause", 10)
                deadline = monotonic() + 5
                while wallet_control._is_open(self.directory) and monotonic() < deadline:
                    sleep(0.01)
                self.assertFalse(wallet_control._is_open(self.directory))
                self.assertFalse(pause.done())
            finally:
                release_debit.set()
            self.assertEqual(operation.result(10).status_code, 200)
            self.assertEqual(pause.result(10), "paused-drained")
        self.assert_paused(self.mobile())
        self.assert_balance("9", 1)

    @override_settings(STRIPE_ENABLED=True, STRIPE_WEBHOOK_SECRET="fixture", PAYPAL_WEBHOOK_ID="fixture")
    def test_provider_routes_still_work_while_wallet_is_paused(self):
        wallet_control.control("pause")
        with patch("monetisation.stripe_payments.create_wallet_topup_checkout",
                   return_value=Mock(url="https://checkout.example.test/", id="cs_test_fixture")) as stripe_topup:
            response = self.api().post("/api/mobile/monetisation/stripe/create-checkout/", {"amount": 10}, format="json")
            self.assertEqual(response.status_code, 200, response.content)
            stripe_topup.assert_called_once()
        with patch("requests.post", return_value=Mock(status_code=201, json=lambda: {"id": "order-fixture"})) as paypal:
            response = self.api().post("/api/mobile/monetisation/paypal/create-order/",
                                       {"type": "credit", "amount": 10}, format="json")
            self.assertEqual(response.status_code, 201, response.content)
            paypal.assert_called_once()
        with patch("monetisation.stripe_payments.stripe.Webhook.construct_event",
                   return_value={"type": "fixture.unhandled"}) as stripe_verify:
            response = self.client.post("/monetisation/stripe/webhook/", {}, content_type="application/json")
            self.assertEqual(response.status_code, 200)
            stripe_verify.assert_called_once()
        with patch("monetisation.refunds._verify_paypal_webhook", return_value=True) as paypal_verify:
            response = self.client.post("/monetisation/paypal/webhook/", {"event_type": "fixture.unhandled"},
                                        content_type="application/json")
            self.assertEqual(response.status_code, 200)
            paypal_verify.assert_called_once()
