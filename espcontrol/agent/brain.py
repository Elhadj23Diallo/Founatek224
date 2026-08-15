from django.utils import timezone
from datetime import timedelta
from espcontrol.models import AgentAlert, AgentConfig


class FounatekBrain:
    def __init__(self, user):
        self.user = user

    def get_cooldown(self):
        """Lit le cooldown depuis AgentConfig, fallback 10 minutes."""
        try:
            return AgentConfig.objects.get(user=self.user).cooldown_minutes
        except AgentConfig.DoesNotExist:
            return 10

    def generate_alerts_from_anomalies(self, device, anomalies):
        count = 0
        cooldown = self.get_cooldown()

        # Cooldown minimum de 1 minute même si AgentConfig = 0
        # pour éviter les doublons dans la même seconde
        effective_cooldown = max(cooldown, 1)

        messages_map = {
            'pm2p5':       "Pic de particules fines détecté (Pollution)",
            'pm10':        "Alerte poussières PM10 élevée",
            'mq135_ppm':   "⚠️ ALERTE GAZ : Niveau de CO2/Fumée critique",
            'humidity':    "Variation anormale de l'humidité",
            'temperature': "Alerte thermique : Température inhabituelle",
        }

        for a in anomalies:
            sensor = a.get("sensor")
            value  = a.get("value")
            msg    = messages_map.get(sensor, f"Anomalie détectée sur {sensor}")

            window_start = timezone.now() - timedelta(minutes=effective_cooldown)

            already_exists = AgentAlert.objects.filter(
                user=self.user,
                device=device,
                sensor=sensor,
                code="BRAIN_ANOMALY",
                created_at__gte=window_start,
            ).exists()

            if already_exists:
                continue  # trop tôt — on ne recrée pas la même alerte

            AgentAlert.objects.create(
                user=self.user,
                device=device,
                sensor=sensor,
                value=value,
                code="BRAIN_ANOMALY",
                message=msg,
                level="CRITICAL",
            )
            count += 1

        return count