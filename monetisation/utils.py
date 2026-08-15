from django.utils import timezone
from .models import Subscription, UsageLog
from datetime import timedelta

# ------------------------------
# ⚡ Définition des limites par plan
# ------------------------------
PLAN_LIMITS = {
    'free': {
        'calls': 100,
        'devices': 1,
        'history_days': 1,
        'alerts': False,
        'marketplace': False,
        'pdf_reports': False,
    },
    'basic': {
        'calls': 1000,
        'devices': 3,
        'history_days': 7,
        'alerts': True,
        'marketplace': False,
        'pdf_reports': False,
    },
    'pro': {
        'calls': 10000,
        'devices': 10,
        'history_days': 30,
        'alerts': True,
        'marketplace': True,
        'pdf_reports': True,
    },
}


# ------------------------------
# ⚡ Récupère les limites du plan de l'utilisateur
# ------------------------------
def get_plan_limits(user):
    sub = Subscription.objects.filter(user=user).first()
    if not sub:
        return PLAN_LIMITS['free']

    plan = sub.plan
    return PLAN_LIMITS.get(plan, PLAN_LIMITS['free'])


# ------------------------------
# ⚡ Vérifie quota API pour la journée
# ------------------------------
def check_api_quota(user):
    limits = get_plan_limits(user)
    max_calls = limits['calls']

    today = timezone.now().date()
    usage, _ = UsageLog.objects.get_or_create(user=user, date=today)

    ok = usage.api_calls < max_calls

    return ok, usage.api_calls, max_calls



# ------------------------------
# ⚡ Vérifie quota appareils
# ------------------------------
# monetisation/utils.py

from espcontrol.models import LED, Relais, Door, Badge

# ------------------------------
# ⚡ Vérifie quota appareils
# ------------------------------
def check_device_quota(user):
    """
    Vérifie si l'utilisateur a atteint la limite d'appareils autorisés par son plan.
    Retourne :
        ok (bool): True si quota pas atteint
        device_count (int): nombre actuel de devices
        max_devices (int): nombre maximal autorisé
    """
    limits = get_plan_limits(user)
    max_devices = limits['devices']

    # Compter tous les "devices" liés à l'utilisateur
    device_count = 0
    device_count += LED.objects.filter(user=user).count()
    device_count += Relais.objects.filter(user=user).count()
    device_count += Door.objects.filter(accesslog__user=user).distinct().count()  # CORRIGÉ
    device_count += Badge.objects.filter(owner=user).count()

    ok = device_count < max_devices
    return ok, device_count, max_devices