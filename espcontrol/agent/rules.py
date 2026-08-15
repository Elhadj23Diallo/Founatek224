# espcontrol/agent/rules.py
from espcontrol.models import SensorRule, AgentAlert, AgentConfig, AppareilData
from django.utils import timezone
from datetime import timedelta


def get_cooldown(user):
    try:
        return AgentConfig.objects.get(user=user).cooldown_minutes
    except AgentConfig.DoesNotExist:
        return 10


def get_moyenne_glissante(device_id, sensor, n=5):
    """Moyenne des N dernières mesures pour ce device + capteur."""
    recent = AppareilData.objects.filter(
        device__device_id=device_id
    ).order_by('-received_at')[:n]

    valeurs = []
    for d in recent:
        val = d.payload.get(sensor)
        if val is None:
            continue
        try:
            valeurs.append(float(val))
        except (TypeError, ValueError):
            continue

    if len(valeurs) < n:
        return None  # Pas assez d'historique → fallback valeur ponctuelle

    return sum(valeurs) / len(valeurs)


def evaluate_rules(observations, user):
    """
    🎯 RÈGLE ABSOLUE :
    Une règle ne peut déclencher une action QUE si :
      1. Elle est ACTIVE
      2. Elle correspond à un device OBSERVÉ dans ce cycle
      3. Le device a un payload contenant le capteur
      4. La VALEUR ACTUELLE dépasse le seuil
      5. La MOYENNE GLISSANTE dépasse aussi le seuil

    ⚡ NOUVEAU : on retourne l'action MÊME en cooldown (avec flag _in_cooldown)
    pour que actions.py puisse maintenir les relais ON sans recréer l'alerte.
    """
    actions  = []
    cooldown = get_cooldown(user)

    iot_devices = observations.get("iot_devices", [])

    # Liste des device_ids observés DANS CE CYCLE
    observed_device_ids = {d["device_id"] for d in iot_devices}

    for device in iot_devices:
        payload   = device.get("payload", {})
        device_id = device["device_id"]

        # ✅ Récupère UNIQUEMENT les règles pour CE device précis (ou globales)
        rules_for_device = SensorRule.objects.filter(
            user=user,
            active=True,
        )

        # Filtre manuel en Python pour gérer device=None
        applicable_rules = []
        for rule in rules_for_device:
            if rule.device is None:
                # Règle globale → s'applique à tous les devices observés
                applicable_rules.append(rule)
            elif rule.device.device_id == device_id:
                # Règle spécifique à ce device
                applicable_rules.append(rule)
            # Sinon : règle pour un AUTRE device → on l'ignore

        for rule in applicable_rules:
            # Capteur disponible dans le payload courant ?
            if rule.sensor not in payload:
                continue

            # Valeur ponctuelle actuelle (priorité absolue)
            value_actuelle = payload.get(rule.sensor)
            if value_actuelle is None:
                continue
            try:
                value_actuelle = float(value_actuelle)
            except (TypeError, ValueError):
                continue

            # 🎯 Sécurité : si la valeur actuelle est SOUS le seuil,
            # on ne déclenche RIEN même si la moyenne historique l'est
            if rule.max_value is not None and value_actuelle <= rule.max_value:
                if rule.min_value is None or value_actuelle >= rule.min_value:
                    continue  # Valeur actuelle dans la plage saine → SKIP

            # Moyenne glissante (filtrage des pics ponctuels)
            moyenne = get_moyenne_glissante(device_id, rule.sensor, n=5)
            if moyenne is None:
                value = value_actuelle
            else:
                value = moyenne

            # 🎯 Double vérification : la moyenne DOIT aussi dépasser le seuil
            triggered = (
                (rule.min_value is not None and value < rule.min_value)
                or
                (rule.max_value is not None and value > rule.max_value)
            )
            if not triggered:
                continue

            # ⚡ Cooldown anti-spam — on vérifie mais on NE SKIPPE PAS
            window_start = timezone.now() - timedelta(minutes=cooldown)
            already_exists = AgentAlert.objects.filter(
                user=user,
                device__device_id=device_id,
                sensor=rule.sensor,
                code=rule.code,
                created_at__gte=window_start,
            ).exists()

            # ✅ MODIFICATION CLÉ : on crée l'action MÊME en cooldown
            # avec un flag pour qu'actions.py sache comment se comporter
            action = build_action(rule, device, value)
            action['_in_cooldown'] = already_exists
            actions.append(action)

    return actions


def build_action(rule, device_data, value):
    return {
        "device_id":  device_data.get("device_id"),
        "sensor":     rule.sensor,
        "value":      round(value, 2),
        "level":      rule.level,
        "message":    rule.message,
        "code":       rule.code,
        "action":     rule.action_type,
        "relais_num": rule.target_num,
    }