# espcontrol/ml/services/air_alerts.py

# Seuils simples (à ajuster plus tard)
THRESHOLDS = {
    "pm2p5": {
        "good": 1.0e-7,
        "warning": 1.5e-7,
    },
    "pm10": {
        "good": 1.5e-7,
        "warning": 2.5e-7,
    },
    "no2": {
        "good": 1.0e-8,
        "warning": 2.0e-8,
    }
}

def evaluate_air_quality(prediction: dict):
    """
    Analyse les prédictions et génère des alertes
    """
    alerts = []
    global_status = "good"

    for pollutant, value in prediction.items():
        if pollutant not in THRESHOLDS:
            continue

        th = THRESHOLDS[pollutant]

        if value > th["warning"]:
            status = "danger"
            message = f"{pollutant.upper()} dépassera un seuil critique dans 3h"
            global_status = "danger"

        elif value > th["good"]:
            status = "warning"
            message = f"{pollutant.upper()} atteindra un niveau préoccupant dans 3h"
            if global_status != "danger":
                global_status = "warning"

        else:
            status = "ok"
            message = f"{pollutant.upper()} restera à un niveau acceptable"

        alerts.append({
            "pollutant": pollutant,
            "value": value,
            "status": status,
            "message": message,
            "thresholds": th
        })

    return {
        "global_status": global_status,
        "alerts": alerts
    }
    
    

def evaluate_air_alert_now(reading):
    """
    Analyse UNE mesure actuelle (réelle ou virtuelle)
    et déclenche une alerte pollution immédiate
    """

    if not reading:
        return None

    if reading.confidence < 0.5:
        return None  # pas assez fiable

    alerts = []

    pollutants = {
        "pm2p5": reading.pm2p5,
        "pm10": reading.pm10,
        "no2": reading.no2,
    }

    global_status = "good"

    for pollutant, value in pollutants.items():
        if pollutant not in THRESHOLDS:
            continue

        th = THRESHOLDS[pollutant]

        if value > th["warning"]:
            status = "danger"
            message = f"{pollutant.upper()} dépasse un seuil critique"
            global_status = "danger"

        elif value > th["good"]:
            status = "warning"
            message = f"{pollutant.upper()} atteint un niveau préoccupant"
            if global_status != "danger":
                global_status = "warning"

        else:
            status = "ok"
            message = f"{pollutant.upper()} à un niveau acceptable"

        alerts.append({
            "pollutant": pollutant,
            "value": value,
            "status": status,
            "message": message,
            "confidence": reading.confidence,
        })

    if global_status == "good":
        return None

    return {
        "global_status": global_status,
        "alerts": alerts,
        "origin": reading.origin,
        "confidence": reading.confidence,
    }

