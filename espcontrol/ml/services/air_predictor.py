import xarray as xr
import pandas as pd
import joblib
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
MODEL_PATH = BASE_DIR / "models" / "cams_conakry_gb.joblib"
DATA_DIR = BASE_DIR / "data" / "cams"

# Charger le modèle UNE FOIS
_pack = joblib.load(MODEL_PATH)
_model = _pack["model"]
_features = _pack["features"]
_targets = _pack["targets"]

def predict_conakry_next_3h():
    # Charger données
    ds_mlev = xr.open_dataset(DATA_DIR / "data_mlev.nc")
    ds_sfc  = xr.open_dataset(DATA_DIR / "data_sfc.nc")

    if "model_level" in ds_mlev.dims:
        ds_mlev = ds_mlev.squeeze("model_level", drop=True)

    ds = xr.merge([ds_mlev, ds_sfc])

    # Conakry
    LAT, LON = 9.64, -13.58
    pt = ds.sel(latitude=LAT, longitude=LON, method="nearest")

    df = pt[_targets].to_dataframe().reset_index()
    df["valid_time"] = pd.to_datetime(df["valid_time"])
    df = df.sort_values("valid_time")

    last = df.iloc[-1].copy()
    last_time = last["valid_time"]

    # Features temps
    last["hour"] = last_time.hour
    last["dayofweek"] = last_time.dayofweek
    last["month"] = last_time.month

    # Lags
    for t in _targets:
        last[f"{t}_lag1"] = df.iloc[-2][t]
        last[f"{t}_lag2"] = df.iloc[-3][t]

    X = pd.DataFrame([last])[_features]
    y_pred = _model.predict(X)[0]

    result = {
        "from_time": last_time.isoformat(),
        "to_time": (last_time + pd.Timedelta(hours=3)).isoformat(),
        "prediction": {t: float(y_pred[i]) for i, t in enumerate(_targets)}
    }

    return result
