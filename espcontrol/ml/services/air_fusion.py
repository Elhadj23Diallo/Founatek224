# espcontrol/ml/services/air_fusion.py

from espcontrol.models import AirReading


def get_latest_air_reading(city_key: str):
    """
    Retourne la meilleure donnée air pour une ville :
    - priorité au capteur réel
    - fallback sur capteur virtuel
    """
    city = city_key.upper()

    # 1️⃣ capteur réel prioritaire
    real = (
        AirReading.objects
        .filter(
            source=f"REAL_SENSOR_{city}",
            is_active=True
        )
        .order_by("-simulated_time")
        .first()
    )

    if real:
        return real

    # 2️⃣ fallback virtuel
    virtual = (
        AirReading.objects
        .filter(
            source=f"VIRTUAL_SENSOR_{city}",
            is_active=True
        )
        .order_by("-simulated_time")
        .first()
    )

    if virtual:
        return virtual

    return None
