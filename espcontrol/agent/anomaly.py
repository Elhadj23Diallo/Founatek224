# espcontrol/agent/anomaly.py
import numpy as np
from espcontrol.models import AppareilData

# ── Plages physiquement saines (OMS) ─────────────────────────────────────────
SAFE_RANGES = {
    'pm2p5':         (0,   25),   # OMS : < 25 µg/m³ = sain
    'pm10':          (0,   50),   # OMS : < 50 µg/m³ = sain
    'mq135_ppm':     (0,  700),   # < 700 ppm = air intérieur acceptable
    'temperature':   (15,  40),   # plage normale Conakry
    'humidity':      (20,  85),   # humidité normale
    'soil_moisture': (0,  100),   # pas de garde pour sol
}

# ── Constantes polynomiales MQ-135 (datasheet fabricant) ─────────────────────
MQ135_A =  -0.000035   # coefficient T²
MQ135_B =   0.005      # coefficient T
MQ135_C =   1.0        # constante
MQ135_D =  -0.002      # coefficient H


def correct_mq135(raw_ppm: float, temperature: float, humidity: float) -> float:
    """
    Correction du capteur MQ-135 en fonction de T° et humidité.

    Le MQ-135 mesure une résistance qui dérive avec la température
    et l'humidité. On calcule un facteur de correction CF basé sur
    les courbes de sensibilité du fabricant :

        CF  = a·T² + b·T + c + d·H
        PPM_corrigé = PPM_brut / CF

    Si CF <= 0 (cas extrême), on retourne la valeur brute sans correction.
    """
    cf = (
        MQ135_A * (temperature ** 2)
        + MQ135_B * temperature
        + MQ135_C
        + MQ135_D * humidity
    )
    if cf <= 0:
        return raw_ppm  # protection contre division par zéro
    return round(raw_ppm / cf, 2)


def correct_pm25(raw_pm25: float, humidity: float) -> float:
    """
    Correction hygroscopique du PM2.5.

    Au-dessus de 70% d'humidité, les particules absorbent l'eau
    et gonflent optiquement — le capteur laser surestime la concentration.

    Formule de correction (Laulainen 1993, reprise par EPA) :
        PM_corrigé = PM_brut / (1 + 0.25 · (H/100))

    En dessous de 70% d'humidité, aucune correction n'est appliquée.
    """
    if humidity <= 70:
        return raw_pm25  # pas d'effet hygroscopique significatif
    correction_factor = 1 + 0.25 * (humidity / 100)
    return round(raw_pm25 / correction_factor, 2)


def get_latest_env(data_points: list) -> tuple:
    """
    Extrait la température et l'humidité les plus récentes
    depuis les données pour les passer aux fonctions de correction.
    Retourne (temperature, humidity) ou (25.0, 50.0) par défaut.
    """
    for d in data_points:
        t = d.payload.get('temperature')
        h = d.payload.get('humidity')
        if t is not None and h is not None:
            return float(t), float(h)
    return 25.0, 50.0   # valeurs par défaut si non disponibles


def detect_anomalies(device, window=100, sigma_threshold=3.0):
    """
    Détecte les anomalies statistiques via Z-score.

    Pipeline complet par ordre d'exécution :
      1. Récupération des N derniers points (fenêtre glissante)
      2. Extraction T° et humidité pour les corrections
      3. Correction MQ-135 (dérive thermique et hygrique)
      4. Correction PM2.5 (hygroscopie si H > 70%)
      5. Garde physique OMS (SAFE_RANGES)
      6. Calcul Z-score sur valeurs corrigées
      7. Marquage is_anomaly en base si Z > seuil
    """
    data_points = list(
        AppareilData.objects.filter(device=device)
        .order_by('-received_at')[:window]
    )
    if len(data_points) < 10:
        return []   # pas assez de données pour un calcul fiable

    # ── Étape 2 : Conditions environnementales pour les corrections ───────────
    temperature, humidity = get_latest_env(data_points)

    sensors = ['pm2p5', 'pm10', 'mq135_ppm', 'humidity', 'temperature', 'soil_moisture']
    anomalies = []

    for sensor in sensors:
        sensor_values = []

        for d in data_points:
            val = d.payload.get(sensor)
            if val is None or not isinstance(val, (int, float)):
                continue

            # ── Étape 3 : Correction MQ-135 ───────────────────────────────────
            if sensor == 'mq135_ppm':
                val = correct_mq135(val, temperature, humidity)

            # ── Étape 4 : Correction PM2.5 hygroscopique ──────────────────────
            elif sensor == 'pm2p5':
                val = correct_pm25(val, humidity)

            sensor_values.append((val, d))

        if len(sensor_values) < 10:
            continue

        values = [v[0] for v in sensor_values]
        mean   = np.mean(values)
        std    = np.std(values)

        latest_value, latest_data = sensor_values[0]

        # ── Étape 5 : Garde physique OMS ──────────────────────────────────────
        safe = SAFE_RANGES.get(sensor)
        if safe and safe[0] <= latest_value <= safe[1]:
            continue   # valeur saine → pas d'anomalie

        # ── Étape 6 : Z-score sur valeur corrigée ─────────────────────────────
        if std < 1.0:
            continue   # signal trop stable → pas d'anomalie significative

        z_score = abs(latest_value - mean) / std

        if z_score > sigma_threshold:
            anomalies.append({
                "sensor":  sensor,
                "value":   latest_value,   # valeur corrigée
                "z_score": round(z_score, 2),
                "id":      latest_data.id,
            })

            # ── Étape 7 : Marquage en base ────────────────────────────────────
            latest_data.is_anomaly = True
            latest_data.save(update_fields=['is_anomaly'])

    return anomalies