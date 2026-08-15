# espcontrol/agent/brain.py

from espcontrol.models import AgentAlert, AppareilData
from django.utils import timezone
from datetime import timedelta


class FounatekBrain:
    """
    Cerveau central IA Founatek
    - Explique
    - Résume
    - Interprète
    """

    def __init__(self, user):
        self.user = user

    # 🧠 1. Résumé global
    def system_summary(self, minutes=60):
        since = timezone.now() - timedelta(minutes=minutes)

        alerts = AgentAlert.objects.filter(
            user=self.user,
            created_at__gte=since
        )

        anomalies = AppareilData.objects.filter(
            device__user=self.user,
            is_anomaly=True,
            received_at__gte=since
        )

        return {
            "alerts_count": alerts.count(),
            "critical_alerts": alerts.filter(level="CRITICAL").count(),
            "anomalies_count": anomalies.count(),
        }

    # 🧠 2. Expliquer une alerte
    def explain_alert(self, alert_id):
        try:
            alert = AgentAlert.objects.get(id=alert_id, user=self.user)
        except AgentAlert.DoesNotExist:
            return "Je ne trouve pas cette alerte."

        explanation = f"""
Alerte **{alert.level}**
Capteur : {alert.sensor}
Valeur mesurée : {alert.value}

Raison :
Le seuil défini dans vos règles a été dépassé.

Recommandation :
Vérifiez l’état du dispositif ou ajustez les seuils si nécessaire.
"""
        return explanation.strip()
