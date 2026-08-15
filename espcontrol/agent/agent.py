# espcontrol/agent/agent.py

from espcontrol.agent.observer import get_latest_observations
from espcontrol.agent.rules import evaluate_rules
from espcontrol.agent.actions import execute_actions


class FounatekAgent:
    """
    Agent IA central Founatek IoT

    Pipeline :
    1. Observer   → collecte des données IoT
    2. Décider    → évaluation des règles dynamiques (SensorRule)
    3. Agir       → création d'alertes / actions
    """

    def __init__(self, user):
        self.user = user

    def run(self):
        # 1️⃣ OBSERVER
        observations = get_latest_observations(self.user)

        # 2️⃣ DÉCIDER
        actions = evaluate_rules(
            observations=observations,
            user=self.user
        )

        # 3️⃣ AGIR
        results = execute_actions(
            actions,
            self.user
        )

        return {
            "observations": observations,
            "decisions": actions,  # OK de garder "decisions" côté output
            "results": results,
        }
