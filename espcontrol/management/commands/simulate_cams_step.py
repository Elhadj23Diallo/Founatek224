from django.core.management.base import BaseCommand
from django.utils import timezone
from espcontrol.models import AirReading
import xarray as xr
import pandas as pd

CAMS_MLEV = "espcontrol/ml/data/cams/data_mlev.nc"
CAMS_SFC  = "espcontrol/ml/data/cams/data_sfc.nc"

LAT = 9.64
LON = -13.58

class Command(BaseCommand):
    help = "Insert one simulated AirReading from CAMS (next timestep)."

    def handle(self, *args, **options):
        ds_mlev = xr.open_dataset(CAMS_MLEV)
        ds_sfc  = xr.open_dataset(CAMS_SFC)

        if "model_level" in ds_mlev.dims:
            ds_mlev = ds_mlev.squeeze("model_level", drop=True)

        ds = xr.merge([ds_mlev, ds_sfc])

        pt = ds.sel(latitude=LAT, longitude=LON, method="nearest")
        df = pt[["pm2p5", "pm10", "co", "no2"]].to_dataframe().reset_index()
        df["valid_time"] = pd.to_datetime(df["valid_time"])
        df = df.sort_values("valid_time").reset_index(drop=True)

        # Chercher quel timestep insérer
        last = AirReading.objects.filter(source="CAMS_SIM").order_by("-simulated_time").first()

        if last is None:
            next_time = df.loc[0, "valid_time"]
        else:
            next_time = last.simulated_time + pd.Timedelta(hours=3)

        row = df[df["valid_time"] == next_time]
        if row.empty:
            # boucle : on recommence au début
            next_time = df.loc[0, "valid_time"]
            row = df[df["valid_time"] == next_time]

        r = row.iloc[0]

        AirReading.objects.create(
            simulated_time=next_time.to_pydatetime(),
            latitude=float(r["latitude"]) if "latitude" in r else float(LAT),
            longitude=float(r["longitude"]) if "longitude" in r else float(LON),
            pm2p5=float(r["pm2p5"]),
            pm10=float(r["pm10"]),
            co=float(r["co"]),
            no2=float(r["no2"]),
            source="CAMS_SIM",
        )

        self.stdout.write(self.style.SUCCESS(f"Inserted CAMS_SIM @ {next_time}"))
