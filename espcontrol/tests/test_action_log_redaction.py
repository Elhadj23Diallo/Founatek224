"""Regression checks for sensitive fields returned by the mobile audit endpoint."""
from django.test import SimpleTestCase

from espcontrol.api_views import _redact_action_log_details


class ActionLogRedactionTests(SimpleTestCase):
    def test_nested_legacy_credentials_are_redacted(self):
        original = {
            "token_key": "sensitive-token",
            "payload": {"api_key": "sensitive-device-key", "temperature": 23},
            "metadata": [{"authorization": "Token sensitive-token"}],
        }
        sanitized = _redact_action_log_details(original)
        self.assertEqual(sanitized["token_key"], "[REDACTED]")
        self.assertEqual(sanitized["payload"]["api_key"], "[REDACTED]")
        self.assertEqual(sanitized["metadata"][0]["authorization"], "[REDACTED]")
        self.assertEqual(sanitized["payload"]["temperature"], 23)
        self.assertEqual(original["token_key"], "sensitive-token")

    def test_unrelated_audit_fields_remain_visible(self):
        self.assertEqual(
            _redact_action_log_details({"device_id": "esp32-1", "event": "sensor_data_received"}),
            {"device_id": "esp32-1", "event": "sensor_data_received"},
        )
