# espcontrol/ml/services/air_simulator.py

import xarray as xr
import pandas as pd
import random
from django.conf import settings
from pathlib import Path
from espcontrol.models import AirReading


# ======================================================
# 1. VILLES AFRICAINES SIMULÉES
# ======================================================

CITIES = {
    "conakry":  {"lat": 9.64,  "lon": -13.58},
    "dakar":    {"lat": 14.69, "lon": -17.44},
    "abidjan":  {"lat": 5.36,  "lon": -4.01},
    "lagos":    {"lat": 6.52,  "lon": 3.38},
    "nairobi":  {"lat": -1.29, "lon": 36.82},
}

STEP = pd.Timedelta(hours=3)

BASE_DIR = Path(settings.BASE_DIR)
DATA_MLEV = BASE_DIR / "espcontrol/ml/data/cams/data_mlev.nc"
DATA_SFC  = BASE_DIR / "espcontrol/ml/data/cams/data_sfc.nc"


# ======================================================
# 2. CACHE DES DATASETS PAR VILLE
# ======================================================

_ds_cache = {}

def _load_city_dataset(city_key: str):
    """
    Charge et met en cache le dataset CAMS pour une ville.
    """
    if city_key in _ds_cache:
        return _ds_cache[city_key]

    if city_key not in CITIES:
        raise ValueError(f"Unknown city: {city_key}")

    ds_mlev = xr.open_dataset(DATA_MLEV)
    ds_sfc = xr.open_dataset(DATA_SFC)

    if "model_level" in ds_mlev.dims:
        ds_mlev = ds_mlev.squeeze("model_level", drop=True)

    ds = xr.merge([ds_mlev, ds_sfc])

    city = CITIES[city_key]

    pt = ds.sel(
        latitude=city["lat"],
        longitude=city["lon"],
        method="nearest"
    )

    _ds_cache[city_key] = pt
    return pt


# ======================================================
# 3. BRUIT CAPTEUR LOW-COST
# ======================================================

def apply_noise(value: float, percent: float) -> float:
    factor = 1 + random.uniform(-percent, percent)
    return max(value * factor, 0.0)


def apply_sensor_noise(row):
    return {
        "pm2p5": apply_noise(float(row.pm2p5), 0.15),
        "pm10":  apply_noise(float(row.pm10),  0.15),
        "co":    apply_noise(float(row.co),    0.10),
        "no2":   apply_noise(float(row.no2),   0.20),
    }


# ======================================================
# 4. SIMULATEUR PRINCIPAL
# ======================================================

def simulator_tick(city_key="conakry"):
    """
    Génère UNE mesure de capteur virtuel pour une ville donnée.
    """
    pt = _load_city_dataset(city_key)

    last = AirReading.objects.filter(
        source=f"VIRTUAL_SENSOR_{city_key.upper()}"
    ).order_by("-simulated_time").first()

    if last:
        next_time = last.simulated_time + STEP
    else:
        next_time = pd.Timestamp("2024-01-31T00:00:00", tz="UTC")

    # ✅ CORRECTION DÉFINITIVE ICI
    # Toujours convertir via pandas pour compatibilité xarray
    next_time_naive = pd.Timestamp(next_time).tz_localize(None)

    row = pt.sel(valid_time=next_time_naive, method="nearest")
    values = apply_sensor_noise(row)

    reading = AirReading.objects.create(
        simulated_time=next_time,
        latitude=float(row.latitude),
        longitude=float(row.longitude),
        pm2p5=values["pm2p5"],
        pm10=values["pm10"],
        co=values["co"],
        no2=values["no2"],

        origin="virtual",
        confidence=0.6,  # 🔑 capteur low-cost simulé
        source=f"VIRTUAL_SENSOR_{city_key.upper()}",
        is_active=True,
    )


    return reading
