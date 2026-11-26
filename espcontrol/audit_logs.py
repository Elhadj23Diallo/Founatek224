def _redact_action_log_details(details):
    """Redact secrets in historical logs without changing stored records."""
    sensitive = ("token", "secret", "password", "authorization", "api_key", "apikey", "credential")
    if isinstance(details, dict):
        return {
            key: "[REDACTED]" if any(part in str(key).lower() for part in sensitive)
            else _redact_action_log_details(value)
            for key, value in details.items()
        }
    if isinstance(details, list):
        return [_redact_action_log_details(item) for item in details]
    return details

def action_log_details_for_display(log):
    if log.action == "ingest":
        details = log.details if isinstance(log.details, dict) else {}
        device_pk = details.get("device_pk")
        result = {"event": "sensor_data_received"}
        if type(device_pk) is int:
            result["device_pk"] = device_pk
        return result
    return _redact_action_log_details(log.details)
