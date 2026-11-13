# monetisation/quota.py
import time

from django.core.cache import cache
from django.db.models import F
from django.utils import timezone
from .models import UsageLog
from monetisation.models import Subscription

DEFAULT_LIMITS = {
    'free': {'calls': 50, 'devices': 1},
    'basic': {'calls': 500, 'devices': 5},
    'pro': {'calls': 10**9, 'devices': 10**9},
}

def get_limits_for_user(user):
    try:
        sub = Subscription.objects.get(user=user)
        plan = sub.plan
    except Exception:
        plan = 'free'
    return DEFAULT_LIMITS.get(plan, DEFAULT_LIMITS['free']), plan

def increment_usage(user, type_action, amount=1):
    today = timezone.now().date()
    usage, _ = UsageLog.objects.get_or_create(user=user, date=today)
    if type_action == 'api':
        usage.api_calls += amount
    elif type_action == 'device':
        usage.device_count += amount
    usage.save()
    return usage

def check_quota(user, type_action, amount=1):
    limits, plan = get_limits_for_user(user)
    today = timezone.now().date()
    usage, _ = UsageLog.objects.get_or_create(user=user, date=today)
    if type_action == 'api':
        if usage.api_calls + amount > limits['calls']:
            return False, plan, usage, limits
    elif type_action == 'device':
        if usage.device_count + amount > limits['devices']:
            return False, plan, usage, limits
    return True, plan, usage, limits


# ---------------- Quota IoT (API matériel : ingestion, relais, LED, accès...) ----------------
# Dimensionné sur ce que fait vraiment un appareil (intervalle d'appel x 86400s/jour),
# pas sur un usage web générique — voir la grille dans la conversation produit.
IOT_LIMITS = {
    'free':  3000,
    'basic': 30000,
    'pro':   200000,
}


def check_iot_quota(user):
    """Vérifie le quota d'appels IoT du jour. Retourne (ok, plan, used, limit)."""
    _, plan = get_limits_for_user(user)
    limit = IOT_LIMITS.get(plan, IOT_LIMITS['free'])
    today = timezone.now().date()
    usage, _ = UsageLog.objects.get_or_create(user=user, date=today)
    return usage.iot_calls < limit, plan, usage.iot_calls, limit


def increment_iot_usage(user):
    """Incrémente iot_calls de façon atomique (UPDATE ... SET iot_calls = iot_calls + 1)
    pour ne pas perdre de compte si deux appareils du même compte écrivent en même temps."""
    today = timezone.now().date()
    usage, _ = UsageLog.objects.get_or_create(user=user, date=today)
    UsageLog.objects.filter(pk=usage.pk).update(iot_calls=F('iot_calls') + 1)
    usage.refresh_from_db(fields=['iot_calls'])
    return usage


# ---------------- Limite de débit pour les appels IoT faits en session web ----------------
# Les appels par session (navigateur connecté) ne comptent pas dans le quota IoT
# journalier (c'est un humain, pas un appareil) mais doivent quand même avoir un
# garde-fou pour éviter qu'un script authentifié par session ne martèle l'API.
SESSION_RATE_LIMIT_PER_MINUTE = 120


def check_session_rate_limit(user):
    """Fenêtre fixe d'une minute, basée sur le cache (partagé entre process via
    FileBasedCache). Retourne (ok, count_dans_la_minute)."""
    bucket = int(time.time() // 60)
    key = f"iot_session_rate:{user.id}:{bucket}"
    try:
        count = cache.incr(key)
    except ValueError:
        cache.set(key, 1, timeout=60)
        count = 1
    return count <= SESSION_RATE_LIMIT_PER_MINUTE, count
