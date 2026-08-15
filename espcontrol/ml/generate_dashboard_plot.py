import xarray as xr
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import joblib
import os

plt.ioff()

# Dossiers
FIG_DIR = "espcontrol/static/air"
os.makedirs(FIG_DIR, exist_ok=True)

# Charger modèle
pack = joblib.load("espcontrol/ml/models/cams_conakry_gb.joblib")
model = pack["model"]
features = pack["features"]
targets = pack["targets"]

# Charger données
ds_mlev = xr.open_dataset("espcontrol/ml/data/cams/data_mlev.nc")
ds_sfc  = xr.open_dataset("espcontrol/ml/data/cams/data_sfc.nc")

if "model_level" in ds_mlev.dims:
    ds_mlev = ds_mlev.squeeze("model_level", drop=True)

ds = xr.merge([ds_mlev, ds_sfc])

LAT, LON = 9.64, -13.58
pt = ds.sel(latitude=LAT, longitude=LON, method="nearest")

df = pt[targets].to_dataframe().reset_index()
df["valid_time"] = pd.to_datetime(df["valid_time"])
df = df.sort_values("valid_time")

# Dernières données (48h)
df_hist = df.tail(16).copy()

# Préparer la prédiction
last = df.iloc[-1].copy()
t0 = last["valid_time"]

last["hour"] = t0.hour
last["dayofweek"] = t0.dayofweek
last["month"] = t0.month

for t in targets:
    last[f"{t}_lag1"] = df.iloc[-2][t]
    last[f"{t}_lag2"] = df.iloc[-3][t]

X = pd.DataFrame([last])[features]
pred = model.predict(X)[0]

t_future = t0 + pd.Timedelta(hours=3)

# ===== GRAPHIQUE PM2.5 (le plus parlant) =====
plt.figure(figsize=(10,4))
plt.plot(df_hist["valid_time"], df_hist["pm2p5"], label="Historique")
plt.scatter(t_future, pred[targets.index("pm2p5")], color="red", label="+3h (prévu)")
plt.title("PM2.5 – Historique & Prévision (+3h)")
plt.xlabel("Temps")
plt.ylabel("PM2.5")
plt.legend()
plt.xticks(rotation=30, ha="right")
plt.tight_layout()

out_path = f"{FIG_DIR}/pm2p5_dashboard.png"
plt.savefig(out_path)
plt.close()

print("Graphique généré :", out_path)
