# espcontrol/agent/actions.py

from datetime import timedelta
from django.utils import timezone
from django.db import transaction

from espcontrol.models import Relais, AgentAlert, Device, ActionLog


def execute_actions(actions, user):
    """
    Exécute les actions décidées par l'agent :
    - création d'alertes
    - actions physiques (relais, etc.)
    """
    results = []

    for item in actions:
        action = item.get("action")

        device_data = item.get("device")
        device = None

        if device_data:
            device = Device.objects.filter(
                device_id=device_data.get("device_id"),
                user=user
            ).first()

        # =========================
        # 🚨 ALERTES DYNAMIQUES (RULE ENGINE)
        # =========================
        if action == "DYNAMIC_ALERT":
            results.append(
                log_alert(
                    user=user,
                    device=device,
                    message=item.get("message"),
                    level=item.get("level", "WARN"),
                    code=item.get("code", "GENERIC"),
                    sensor=item.get("sensor"),
                    value=item.get("value"),
                )
            )

        # =========================
        # 💧 ACTION PHYSIQUE
        # =========================
        elif action == "START_IRRIGATION":
            # Preferer l'exécution asynchrone via Celery si disponible
            try:
                from espcontrol import tasks

                if hasattr(tasks, "start_irrigation_task") and hasattr(tasks.start_irrigation_task, "delay"):
                    # enqueue
                    task = tasks.start_irrigation_task.delay(user.id)
                    results.append(f"Tâche irrigation lancée: {task.id}")
                else:
                    # fallback synchrone
                    results.append(start_irrigation(user))
            except Exception:
                # fallback synchrone si import fail
                results.append(start_irrigation(user))

        else:
            results.append(f"Action inconnue : {action}")

    return results


def start_irrigation(user):
    """
    Active le relais d'irrigation (ex: relais n°1)
    """
    # Opération atomique et journalisée
    try:
        with transaction.atomic():
            relais = Relais.objects.get(user=user, num=1)
            relais.etat = True
            relais.save(update_fields=["etat"])

            # Log action
            try:
                ActionLog.objects.create(
                    user=user,
                    action="START_IRRIGATION",
                    details={"relais_num": relais.num}
                )
            except Exception:
                pass

            return "Irrigation activée"
    except Relais.DoesNotExist:
        return "Relais irrigation introuvable"


def log_alert(
    user,
    message,
    device=None,
    level="WARN",
    code="GENERIC",
    sensor=None,
    value=None,
):
    """
    Crée une alerte SI elle n'existe pas déjà (anti-spam)
    """

    # 🔒 DÉDUPLICATION / COOLDOWN : une seule alerte active par règle violée
    # On ignore si une alerte du même code/sensor a été créée récemment (fenêtre)
    try:
        cooldown_minutes = 10
        window_start = timezone.now() - timedelta(minutes=cooldown_minutes)

        recent_exists = AgentAlert.objects.filter(
            user=user,
            device=device,
            sensor=sensor,
            code=code,
            created_at__gte=window_start,
        ).exists()

        if recent_exists:
            return f"Alerte récente existante ignorée (cooldown {cooldown_minutes}m): {message}"

        alert = AgentAlert.objects.create(
            user=user,
            device=device,
            message=message,
            level=level,
            code=code,
            sensor=sensor,
            value=value,
        )

        # Log action
        try:
            ActionLog.objects.create(
                user=user,
                action="CREATE_ALERT",
                details={"alert_id": alert.id, "code": code, "sensor": sensor, "value": value},
            )
        except Exception:
            pass

        return f"Alerte créée : {message}"
    except Exception as e:
        return f"Erreur création alerte: {e}"
