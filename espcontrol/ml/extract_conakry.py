import xarray as xr
import pandas as pd

# Chemins
PATH_MLEV = "espcontrol/ml/data/cams/data_mlev.nc"
PATH_SFC  = "espcontrol/ml/data/cams/data_sfc.nc"

# Charger
ds_mlev = xr.open_dataset(PATH_MLEV)
ds_sfc  = xr.open_dataset(PATH_SFC)

# Supprimer model_level (inutile ici)
if "model_level" in ds_mlev.dims:
    ds_mlev = ds_mlev.squeeze("model_level", drop=True)

# Fusionner
ds = xr.merge([ds_mlev, ds_sfc])

# Coordonnées Conakry
LAT = 9.64
LON = -13.58

# Sélection du point le plus proche
pt = ds.sel(latitude=LAT, longitude=LON, method="nearest")

# Variables utiles
vars_keep = ["pm2p5", "pm10", "co", "no2", "go3"]

# Conversion en DataFrame
df = pt[vars_keep].to_dataframe().reset_index()

# Convertir le temps
df["valid_time"] = pd.to_datetime(df["valid_time"])

# Trier
df = df.sort_values("valid_time")

print("Aperçu des données Conakry :")
print(df.head())

print("\nInfos générales :")
print(df.info())
