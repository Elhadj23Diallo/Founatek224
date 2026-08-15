# espcontrol/agent/actions.py
from datetime import timedelta
from django.utils import timezone
from django.db import transaction
from espcontrol.models import Relais, AgentAlert, Device, ActionLog, AgentConfig


def get_cooldown(user):
    """Lit le cooldown depuis AgentConfig, fallback 10 minutes."""
    try:
        config = AgentConfig.objects.get(user=user)
        return config.cooldown_minutes
    except AgentConfig.DoesNotExist:
        return 10


def execute_actions(actions, user):
    """
    Logique NEXUS :
    1. Active les relais critiques (TOUJOURS, même en cooldown).
    2. Crée les alertes (UNIQUEMENT si pas en cooldown).
    3. Éteint automatiquement tout relais ON qui n'est plus critique.
    
    ✅ AMÉLIORATIONS :
    - Déduplication des actions identiques dans le même cycle
    - Les relais restent ON tant que la pollution dure (même si cooldown alerte)
    - Le balayage de sécurité ne s'applique qu'aux relais hors urgence active
    """
    results = []
    active_critical_relais = []  # liste des num de relais qui doivent rester ON
    
    # ✅ Déduplication : on garde une seule action par (device_id, sensor, code)
    seen_keys = set()
    deduped_actions = []
    for item in actions:
        key = (
            item.get("device_id"),
            item.get("sensor"),
            item.get("code"),
        )
        if key not in seen_keys:
            seen_keys.add(key)
            deduped_actions.append(item)

    # --- 1. ANALYSE DES ACTIONS ---
    for item in deduped_actions:
        action      = item.get("action")
        device_id   = item.get("device_id")
        level       = item.get("level", "WARN")
        in_cooldown = item.get("_in_cooldown", False)  # ✅ NOUVEAU
        device      = None

        if device_id:
            device = Device.objects.filter(device_id=device_id, user=user).first()

        if not device:
            continue  # device inconnu → on ignore

        # ✅ Insensible à la casse — accepte 'alert' / 'ALERT' / 'Alert'
        action_upper = action.upper() if action else ""

        # ── 🚨 ALERTES Dashboard ──
        # On crée l'alerte UNIQUEMENT si pas en cooldown
        # Sinon, alerte déjà en base → on ne fait rien côté alerte
        if action_upper in ["ALERT", "DYNAMIC_ALERT", "START_IRRIGATION"] and not in_cooldown:
            results.append(
                log_alert(
                    user, item.get("message"), device, level,
                    item.get("code"), item.get("sensor"), item.get("value")
                )
            )

        # ── ⚡ ACTIVATION RELAIS (CRITICAL uniquement) ──
        # TOUJOURS exécuté pour les CRITICAL, même en cooldown
        # → c'est ce qui permet aux relais de rester ON tant que ça pollue
        if action_upper == "START_IRRIGATION" and level == "CRITICAL":
            target_num = item.get("relais_num", 1)
            if target_num:  # Sécurité : target_num doit être défini
                active_critical_relais.append(target_num)
                results.append(toggle_relais(user, target_num, state=True, device=device))

    # --- 2. BALAYAGE DE SÉCURITÉ — TOUJOURS EXÉCUTÉ ---
    # Éteint tout relais ON qui n'est plus dans la liste des urgences actives
    # ⚡ active_critical_relais est maintenant rempli même en cooldown
    # → les relais correctement maintenus, balayage uniquement si plus aucune urgence
    tous_les_relais = Relais.objects.filter(user=user, etat=True)
    for r in tous_les_relais:
        if r.num not in active_critical_relais:
            results.append(toggle_relais(user, r.num, state=False))

    return results


def toggle_relais(user, num=1, state=True, device=None):
    """
    Modifie l'état du relais par user + num.
    Le champ device n'existe pas sur le modèle Relais —
    il est passé uniquement pour enrichir le log ActionLog.
    """
    try:
        with transaction.atomic():
            relais = Relais.objects.get(user=user, num=num)

            if relais.etat == state:
                return f"Statu Quo : {relais.nom} est deja {'ON' if state else 'OFF'}"

            relais.etat = state
            relais.save(update_fields=["etat"])

            ActionLog.objects.create(
                user=user,
                action="START_IRRIGATION" if state else "STOP_IRRIGATION",
                details={
                    "relais_num":   num,
                    "nom_appareil": relais.nom,
                    "device_id":    device.device_id if device else "inconnu",
                    "auto":         True,
                    "info":         "IA : Retour securite (OFF)" if not state else "IA : Alerte Critique (ON)",
                }
            )
            return f"Succes : {relais.nom} -> {'ON' if state else 'OFF'}"

    except Relais.DoesNotExist:
        return f"Erreur : Relais {num} introuvable pour cet utilisateur"


def log_alert(user, message, device=None, level="WARN", code="GENERIC", sensor=None, value=None):
    """
    Crée une alerte avec cooldown lu depuis AgentConfig.
    
    Anti-spam à 2 niveaux :
    - Anti-doublon exact (même code + non lue déjà existante)
    - Cooldown temporel (même code dans la fenêtre N minutes)
    """

    # ── 1. Anti-doublon EXACT ──
    active_exact = AgentAlert.objects.filter(
        user=user,
        device=device,
        sensor=sensor,
        code=code,
        is_read=False
    ).exists()
    if active_exact:
        return f"Info : Alerte '{code}' deja active non lue"

    # ── 2. Cooldown temporel ──
    cooldown     = get_cooldown(user)
    window_start = timezone.now() - timedelta(minutes=cooldown)
    recent_same_code = AgentAlert.objects.filter(
        user=user,
        device=device,
        sensor=sensor,
        code=code,
        created_at__gte=window_start
    ).exists()
    if recent_same_code:
        return f"Cooldown actif pour '{code}'"

    # ── 3. Création de l'alerte ──
    AgentAlert.objects.create(
        user=user,
        device=device,
        message=message,
        level=level,
        code=code,
        sensor=sensor,
        value=value
    )
    return f"Alerte '{code}' [{level}] enregistree"