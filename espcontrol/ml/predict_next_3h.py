import xarray as xr
import pandas as pd
import joblib

# Charger le modèle
MODEL_PATH = "espcontrol/ml/cams_conakry_gb.joblib"
pack = joblib.load(MODEL_PATH)
model = pack["model"]
feature_cols = pack["features"]
targets = pack["targets"]

# Charger les données
PATH_MLEV = "espcontrol/ml/data/cams/data_mlev.nc"
PATH_SFC  = "espcontrol/ml/data/cams/data_sfc.nc"

ds_mlev = xr.open_dataset(PATH_MLEV)
ds_sfc  = xr.open_dataset(PATH_SFC)

if "model_level" in ds_mlev.dims:
    ds_mlev = ds_mlev.squeeze("model_level", drop=True)

ds = xr.merge([ds_mlev, ds_sfc])

# Conakry
LAT = 9.64
LON = -13.58
pt = ds.sel(latitude=LAT, longitude=LON, method="nearest")

df = pt[["pm2p5", "pm10", "co", "no2"]].to_dataframe().reset_index()
df["valid_time"] = pd.to_datetime(df["valid_time"])
df = df.sort_values("valid_time")

# Dernière ligne connue
last = df.iloc[-1].copy()
last_time = last["valid_time"]

# Features temporelles
last["hour"] = last_time.hour
last["dayofweek"] = last_time.dayofweek
last["month"] = last_time.month

# Lags
for t in targets:
    last[f"{t}_lag1"] = df.iloc[-2][t]
    last[f"{t}_lag2"] = df.iloc[-3][t]

# Construire X
X_pred = pd.DataFrame([last])[feature_cols]

# Prédiction
y_pred = model.predict(X_pred)[0]

print("=== PRÉDICTION CONAKRY ===")
print(f"À partir de : {last_time}")
print(f"Prévision pour : {last_time + pd.Timedelta(hours=3)}\n")

for i, t in enumerate(targets):
    print(f"{t} prévu : {y_pred[i]:.6e}")
