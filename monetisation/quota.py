# monetisation/quota.py
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
