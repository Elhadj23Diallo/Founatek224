try:
    # Optional: if Celery is installed and configured, register a real task
    from celery import shared_task
    CELERY_AVAILABLE = True
except Exception:
    shared_task = None
    CELERY_AVAILABLE = False

from django.db import transaction
from espcontrol.models import Relais, ActionLog, Device


def _start_irrigation_internal(user_id):
    from django.contrib.auth import get_user_model
    User = get_user_model()
    try:
        user = User.objects.get(id=user_id)
    except Exception:
        return "Utilisateur introuvable"

    try:
        with transaction.atomic():
            relais = Relais.objects.get(user=user, num=1)
            relais.etat = True
            relais.save(update_fields=["etat"])
            try:
                ActionLog.objects.create(user=user, action="START_IRRIGATION", details={"relais_num": relais.num})
            except Exception:
                pass
            return "Irrigation activée"
    except Relais.DoesNotExist:
        return "Relais irrigation introuvable"


if CELERY_AVAILABLE:
    @shared_task(name="espcontrol.start_irrigation_task")
    def start_irrigation_task(user_id):
        return _start_irrigation_internal(user_id)
else:
    # fallback callable compatible with .delay attribute absence
    def start_irrigation_task(user_id):
        return _start_irrigation_internal(user_id)
