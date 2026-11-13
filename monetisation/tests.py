from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from espcontrol.models import Device, LED, Relais
from monetisation.models import UsageLog
from monetisation.quota import (
    check_iot_quota,
    increment_iot_usage,
    check_session_rate_limit,
    IOT_LIMITS,
    SESSION_RATE_LIMIT_PER_MINUTE,
)
from monetisation.utils import check_device_quota

User = get_user_model()


class IotQuotaMiddlewareTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="iot-quota-user", password="test-pass-123")
        self.token, _ = Token.objects.get_or_create(user=self.user)
        self.api_client = APIClient()
        self.api_client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")

    def test_iot_call_via_token_increments_usage_and_blocks_over_limit(self):
        today = timezone.now().date()
        UsageLog.objects.update_or_create(
            user=self.user, date=today, defaults={"iot_calls": IOT_LIMITS["free"] - 1}
        )

        resp_ok = self.api_client.post(
            "/api/iot/ingest/",
            {"device_id": "quota-dev", "data": {"temperature": 20}},
            format="json",
        )
        self.assertIn(resp_ok.status_code, (200, 201))
        self.assertEqual(UsageLog.objects.get(user=self.user, date=today).iot_calls, IOT_LIMITS["free"])

        resp_blocked = self.api_client.post(
            "/api/iot/ingest/",
            {"device_id": "quota-dev", "data": {"temperature": 21}},
            format="json",
        )
        self.assertEqual(resp_blocked.status_code, 429)
        self.assertEqual(resp_blocked.json()["plan"], "free")

    def test_iot_call_via_session_is_not_counted(self):
        self.client.force_login(self.user)
        today = timezone.now().date()

        self.client.post(
            "/api/iot/ingest/",
            {"device_id": "session-dev", "data": {"temperature": 20}},
            content_type="application/json",
        )

        self.assertFalse(UsageLog.objects.filter(user=self.user, date=today).exists())

    def test_non_iot_api_path_is_not_counted_even_with_token(self):
        today = timezone.now().date()

        resp = self.api_client.get("/api/mobile/air-quality-summary/")

        self.assertEqual(resp.status_code, 200)
        self.assertFalse(UsageLog.objects.filter(user=self.user, date=today).exists())

    def test_check_iot_quota_reports_plan_and_limit(self):
        ok, plan, used, limit = check_iot_quota(self.user)
        self.assertTrue(ok)
        self.assertEqual(plan, "free")
        self.assertEqual(used, 0)
        self.assertEqual(limit, IOT_LIMITS["free"])

        increment_iot_usage(self.user)
        _, _, used, _ = check_iot_quota(self.user)
        self.assertEqual(used, 1)


class SessionRateLimitTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="session-rate-user", password="test-pass-123")
        cache.clear()

    def tearDown(self):
        cache.clear()

    def test_allows_up_to_the_limit_then_blocks(self):
        for _ in range(SESSION_RATE_LIMIT_PER_MINUTE):
            ok, _ = check_session_rate_limit(self.user)
            self.assertTrue(ok)

        ok, count = check_session_rate_limit(self.user)
        self.assertFalse(ok)
        self.assertEqual(count, SESSION_RATE_LIMIT_PER_MINUTE + 1)

    def test_session_call_over_limit_returns_429(self):
        self.client.force_login(self.user)
        for _ in range(SESSION_RATE_LIMIT_PER_MINUTE):
            check_session_rate_limit(self.user)

        resp = self.client.get("/api/led/")

        self.assertEqual(resp.status_code, 429)
        self.assertIn("limit_per_minute", resp.json())


class DeviceQuotaTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="device-quota-user", password="test-pass-123")

    def test_counts_real_devices_not_legacy_models(self):
        Device.objects.create(user=self.user, device_id="d1", name="Capteur 1")
        Device.objects.create(user=self.user, device_id="d2", name="Capteur 2")
        LED.objects.create(user=self.user)
        Relais.objects.create(user=self.user, num=1, nom="Relais test")

        ok, device_count, max_devices = check_device_quota(self.user)

        self.assertEqual(device_count, 2)
        self.assertEqual(max_devices, 1)  # plan free
        self.assertFalse(ok)
