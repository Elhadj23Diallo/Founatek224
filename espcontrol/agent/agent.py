# espcontrol/agent/agent.py
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
        print(f"--- 🤖 Démarrage de l'agent pour {self.user.username} ---")

        # 1️⃣ OBSERVER
        observations = get_latest_observations(self.user)
        print(f"Observations collectées : {len(observations.get('iot_devices', []))} appareils trouvés.")

        # 2️⃣ DÉCIDER (Règles fixes SensorRule)
        actions = evaluate_rules(observations=observations, user=self.user)
        if actions:
            print(f"Décisions basées sur les règles : {len(actions)} actions prévues.")

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
                print(f"⚠️ Erreur : Device {dev_obs['device_id']} introuvable en base.")
            except Exception as e:
                print(f"❌ Erreur IA sur {dev_obs.get('device_id')} : {e}")

        if ia_alerts_count > 0:
            print(f"Intelligence : {ia_alerts_count} nouvelles alertes d'anomalies créées.")

        # 4️⃣ AGIR (Exécution des actions physiques ou log d'alertes)
        results = execute_actions(actions, self.user)

        return {
            "observations": observations,
            "decisions": actions,
            "results": results,
            "ia_alerts_created": ia_alerts_count
        }