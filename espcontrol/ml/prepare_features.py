import xarray as xr
import pandas as pd

# Charger les fichiers
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

# DataFrame
df = pt[["pm2p5", "pm10", "co", "no2", "go3"]].to_dataframe().reset_index()
df["valid_time"] = pd.to_datetime(df["valid_time"])
df = df.sort_values("valid_time")

# -----------------------
# FEATURES TEMPORELLES
# -----------------------
df["hour"] = df["valid_time"].dt.hour
df["dayofweek"] = df["valid_time"].dt.dayofweek
df["month"] = df["valid_time"].dt.month

# -----------------------
# LAGS (valeurs passées)
# -----------------------
targets = ["pm2p5", "pm10", "co", "no2"]

for t in targets:
    df[f"{t}_lag1"] = df[t].shift(1)  # t-3h
    df[f"{t}_lag2"] = df[t].shift(2)  # t-6h

# -----------------------
# SUPPRIMER LES LIGNES INCOMPLÈTES
# -----------------------
df_features = df.dropna().reset_index(drop=True)

print("Aperçu des features prêtes :")
print(df_features.head())

print("\nColonnes finales :")
print(df_features.columns)

print("\nNombre de lignes :", len(df_features))
