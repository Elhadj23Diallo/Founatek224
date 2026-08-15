# espcontrol/agent/observer.py

from espcontrol.models import (
    DHTData,
    SoilData,
    SensorData,
    AppareilData,
)

def get_latest_observations(user):
    """
    Collecte toutes les observations utiles pour l'agent IA
    """
    obs = {
        "temperature": None,
        "humidity_air": None,
        "soil_moisture": None,
        "co2": None,
        "iot_devices": [],
    }

    # =========================
    # 1️⃣ PRIORITÉ : AppareilData (ESP32 / IoT universel)
    # =========================
    latest_payloads = (
        AppareilData.objects
        .filter(device__user=user)
        .select_related("device")
        .order_by("device__device_id", "-received_at")
    )

    used_devices = set()

    for data in latest_payloads:
        device_id = data.device.device_id

        if device_id in used_devices:
            continue

        payload = data.payload or {}

        # 🔁 Mapping automatique global
        obs["temperature"] = obs["temperature"] or payload.get("temperature")
        obs["humidity_air"] = obs["humidity_air"] or payload.get("humidity")
        obs["soil_moisture"] = obs["soil_moisture"] or payload.get("soil_moisture")
        obs["co2"] = obs["co2"] or payload.get("mq135_ppm")

        obs["iot_devices"].append({
            "device_id": device_id,
            "device_name": data.device.name,
            "payload": payload,
            "is_anomaly": data.is_anomaly,
            "received_at": data.received_at,
        })

        used_devices.add(device_id)

    # =========================
    # 2️⃣ FALLBACK anciens modèles (si existants)
    # =========================
    if obs["temperature"] is None:
        obs["temperature"] = (
            DHTData.objects.filter(user=user)
            .order_by("-created_at")
            .values_list("temperature", flat=True)
            .first()
        )

    if obs["soil_moisture"] is None:
        obs["soil_moisture"] = (
            SoilData.objects.filter(user=user)
            .order_by("-created_at")
            .values_list("humidity", flat=True)
            .first()
        )

    if obs["co2"] is None:
        obs["co2"] = (
            SensorData.objects.filter(user=user)
            .order_by("-timestamp")
            .values_list("co2", flat=True)
            .first()
        )

    return obs
