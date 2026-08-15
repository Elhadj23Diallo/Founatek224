import pandas as pd
import matplotlib
matplotlib.use("Agg")  # IMPORTANT pour PythonAnywhere
import matplotlib.pyplot as plt
import xarray as xr
import os

# Dossier de sortie
OUTPUT_DIR = "espcontrol/ml/figures"
os.makedirs(OUTPUT_DIR, exist_ok=True)

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

df = pt[["pm2p5", "pm10", "co", "no2", "go3"]].to_dataframe().reset_index()
df["valid_time"] = pd.to_datetime(df["valid_time"])
df = df.sort_values("valid_time")

# Variables à tracer
variables = ["pm2p5", "pm10", "co", "no2", "go3"]

for var in variables:
    plt.figure(figsize=(10, 4))
    plt.plot(df["valid_time"], df[var])
    plt.title(f"{var.upper()} - Conakry (CAMS)")
    plt.xlabel("Temps")
    plt.ylabel(var)
    plt.xticks(rotation=30, ha="right")
    plt.tight_layout()

    filename = f"{OUTPUT_DIR}/{var}_conakry.png"
    plt.savefig(filename)
    plt.close()

    print(f"Courbe sauvegardée : {filename}")
