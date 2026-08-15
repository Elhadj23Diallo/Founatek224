from espcontrol.models import (
    DHTData,
    SoilData,
    SensorData,
    AppareilData,
)

def get_latest_observations(user):

    obs = {
        "temperature": None,
        "humidity_air": None,
        "soil_moisture": None,
        "co2": None,

        # 🌫 SDS011
        "pm2p5": None,
        "pm10": None,

        # 🧠 AUTO-ADAPTATION (IMPORTANT)
        "available_sensors": set(),

        "iot_devices": [],
    }

    latest_payloads = AppareilData.objects.filter(
        device__user=user
    ).select_related("device").order_by("device_id", "-received_at")

    seen = set()

    for data in latest_payloads:

        device_id = data.device.device_id

        if device_id in seen:
            continue

        seen.add(device_id)

        payload = data.payload or {}

        # =========================
        # 🧠 AUTO SENSOR DETECTION
        # =========================
        obs["available_sensors"].update(payload.keys())

        # =========================
        # 🌱 capteurs classiques
        # =========================
        if obs["temperature"] is None:
            obs["temperature"] = payload.get("temperature")

        if obs["humidity_air"] is None:
            obs["humidity_air"] = payload.get("humidity")

        if obs["soil_moisture"] is None:
            obs["soil_moisture"] = payload.get("soil_moisture")

        if obs["co2"] is None:
            obs["co2"] = payload.get("mq135_ppm")

        # =========================
        # 🌫 SDS011 (air quality)
        # =========================
        if obs["pm2p5"] is None:
            obs["pm2p5"] = payload.get("pm2p5")

        if obs["pm10"] is None:
            obs["pm10"] = payload.get("pm10")

        # =========================
        # devices list
        # =========================
        obs["iot_devices"].append({
            "device_id": device_id,
            "device_name": data.device.name,
            "payload": payload,
            "is_anomaly": data.is_anomaly,
            "received_at": data.received_at,
        })

    # =========================
    # fallback anciens modèles
    # =========================
    if obs["temperature"] is None:
        obs["temperature"] = DHTData.objects.filter(user=user)\
            .order_by("-created_at")\
            .values_list("temperature", flat=True)\
            .first()

    if obs["soil_moisture"] is None:
        obs["soil_moisture"] = SoilData.objects.filter(user=user)\
            .order_by("-created_at")\
            .values_list("humidity", flat=True)\
            .first()

    if obs["co2"] is None:
        obs["co2"] = SensorData.objects.filter(user=user)\
            .order_by("-timestamp")\
            .values_list("co2", flat=True)\
            .first()

    return obs