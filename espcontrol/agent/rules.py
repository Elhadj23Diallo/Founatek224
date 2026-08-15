# espcontrol/agent/rules.py

from espcontrol.models import SensorRule

def evaluate_rules(observations, user):
    actions = []
    rules = SensorRule.objects.filter(user=user, active=True)

    for device in observations.get("iot_devices", []):
        payload = device.get("payload", {})

        for rule in rules:
            # règle globale ou spécifique device
            if rule.device and rule.device.device_id != device["device_id"]:
                continue

            value = payload.get(rule.sensor)
            if value is None:
                continue

            if rule.min_value is not None and value < rule.min_value:
                actions.append(build_action(rule, device, value))

            if rule.max_value is not None and value > rule.max_value:
                actions.append(build_action(rule, device, value))

    return actions


def build_action(rule, device, value):
    return {
        "action": "DYNAMIC_ALERT",
        "device": device,
        "sensor": rule.sensor,
        "value": value,
        "level": rule.level,
        "message": rule.message,
        "code": rule.code,
    }
