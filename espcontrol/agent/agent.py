# espcontrol/agent/agent.py
import logging

logger = logging.getLogger(__name__)

from espcontrol.agent.observer import get_latest_observations
from espcontrol.agent.rules import evaluate_rules
from espcontrol.agent.actions import execute_actions
from espcontrol.agent.anomaly import detect_anomalies
from espcontrol.agent.brain import FounatekBrain
from espcontrol.models import Device

class FounatekAgent:
    def __init__(self, user):
        self.user = user
        self.brain = FounatekBrain(user)

    def run(self):
        logger.info("Démarrage de l'agent pour %s", self.user.username)

        # 1️⃣ OBSERVER
        observations = get_latest_observations(self.user)
        logger.info("Observations collectées : %s appareils", len(observations.get('iot_devices', [])))

        # 2️⃣ DÉCIDER (Règles fixes SensorRule)
        actions = evaluate_rules(observations=observations, user=self.user)
        if actions:
            logger.info("Règles : %s actions prévues", len(actions))

        # 3️⃣ APPRENDRE & DÉTECTER (Intelligence Artificielle)
        ia_alerts_count = 0
        for dev_obs in observations.get("iot_devices", []):
            try:
                # Récupération sécurisée du device (pour éviter les erreurs de multi-user)
                device_obj = Device.objects.get(device_id=dev_obs['device_id'], user=self.user)

                # Analyse mathématique (Z-Score)
                anomalies = detect_anomalies(device_obj)

                if anomalies:
                    # Envoi au cerveau pour générer les alertes AgentAlert
                    created_alerts = self.brain.generate_alerts_from_anomalies(device_obj, anomalies)
                    ia_alerts_count += created_alerts
            except Device.DoesNotExist:
                logger.warning("Appareil %s introuvable en base", dev_obs['device_id'])
            except Exception as e:
                logger.exception("Erreur IA sur l'appareil %s : %s", dev_obs.get('device_id'), e)

        if ia_alerts_count > 0:
            logger.info("%s nouvelles alertes d'anomalie créées", ia_alerts_count)

        # 4️⃣ AGIR (Exécution des actions physiques ou log d'alertes)
        results = execute_actions(actions, self.user)

        return {
            "observations": observations,
            "decisions": actions,
            "results": results,
            "ia_alerts_created": ia_alerts_count
        }