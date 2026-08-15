import xarray as xr
import pandas as pd
from sklearn.multioutput import MultiOutputRegressor
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_absolute_error
import joblib

# -----------------------
# CHARGEMENT DES DONNÉES
# -----------------------
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

# -----------------------
# FEATURES
# -----------------------
df["hour"] = df["valid_time"].dt.hour
df["dayofweek"] = df["valid_time"].dt.dayofweek
df["month"] = df["valid_time"].dt.month

targets = ["pm2p5", "pm10", "co", "no2"]

for t in targets:
    df[f"{t}_lag1"] = df[t].shift(1)
    df[f"{t}_lag2"] = df[t].shift(2)

df = df.dropna().reset_index(drop=True)

feature_cols = ["hour", "dayofweek", "month"]
for t in targets:
    feature_cols += [f"{t}_lag1", f"{t}_lag2"]

X = df[feature_cols]
Y = df[targets]

# -----------------------
# SPLIT TEMPOREL
# -----------------------
split_idx = int(len(df) * 0.8)
X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
Y_train, Y_test = Y.iloc[:split_idx], Y.iloc[split_idx:]

# -----------------------
# MODÈLE ROBUSTE
# -----------------------
base_model = HistGradientBoostingRegressor(
    max_depth=6,
    learning_rate=0.08,
    max_iter=300,
    random_state=42
)

model = MultiOutputRegressor(base_model)
model.fit(X_train, Y_train)

# -----------------------
# ÉVALUATION
# -----------------------
pred = model.predict(X_test)

print("=== MAE (+3h) — Gradient Boosting ===")
for i, t in enumerate(targets):
    mae = mean_absolute_error(Y_test[t], pred[:, i])
    print(f"{t} : MAE = {mae:.6e}")

# -----------------------
# SAUVEGARDE
# -----------------------
joblib.dump(
    {
        "model": model,
        "features": feature_cols,
        "targets": targets,
        "step_hours": 3,
        "location": "Conakry"
    },
    "espcontrol/ml/cams_conakry_gb.joblib"
)

print("\n✅ Modèle robuste sauvegardé : espcontrol/ml/cams_conakry_gb.joblib")
