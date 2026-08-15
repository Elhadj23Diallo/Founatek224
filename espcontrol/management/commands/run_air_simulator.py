from django.core.management.base import BaseCommand
from espcontrol.ml.services.air_simulator import simulator_tick, CITIES

class Command(BaseCommand):
    help = "Run air quality virtual sensor simulator for all cities"

    def handle(self, *args, **options):
        self.stdout.write("🌍 Starting air simulator...")

        for city in CITIES.keys():
            try:
                reading = simulator_tick(city)
                self.stdout.write(
                    f"✅ {city.upper()} @ {reading.simulated_time}"
                )
            except Exception as e:
                self.stderr.write(
                    f"❌ {city.upper()} failed: {e}"
                )

        self.stdout.write("🏁 Air simulator finished.")
