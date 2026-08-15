import xarray as xr
import pandas as pd

# Chemins
PATH_MLEV = "espcontrol/ml/data/cams/data_mlev.nc"
PATH_SFC  = "espcontrol/ml/data/cams/data_sfc.nc"

# Charger les datasets
ds_mlev = xr.open_dataset(PATH_MLEV)
ds_sfc  = xr.open_dataset(PATH_SFC)

print("=== DATA MLEV ===")
print(ds_mlev)
print("\nVariables MLEV :", list(ds_mlev.data_vars))

print("\n=== DATA SFC ===")
print(ds_sfc)
print("\nVariables SFC :", list(ds_sfc.data_vars))

# Infos temps
time_name = "valid_time"
times = pd.to_datetime(ds_sfc[time_name].values)

print("\n=== TEMPS ===")
print("Début :", times.min())
print("Fin   :", times.max())
print("Pas dominant :")
print(pd.Series(times).diff().value_counts().head())
