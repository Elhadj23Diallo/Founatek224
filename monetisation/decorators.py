# monetisation/decorators.py
from functools import wraps
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from .models import Subscription
from .quota import check_quota, increment_usage
from .utils import get_plan_limits, check_api_quota, check_device_quota

# ---------------- plan_required ----------------
def plan_required(allowed_plans):
    """
    Vérifie si l'utilisateur a un plan autorisé pour accéder à la vue.
    allowed_plans: liste de plans autorisés ['basic', 'pro']
    Les superusers ont toujours accès.
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return JsonResponse(
                    {'error': 'Utilisateur non authentifié.'},
                    status=403,
                    json_dumps_params={'ensure_ascii': False}
                )

            # Les superusers ont accès direct
            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)

            subscription, _ = Subscription.objects.get_or_create(user=request.user)
            if subscription.plan not in allowed_plans:
                return JsonResponse(
                    {
                        'error': 'Votre plan actuel ne permet pas d’accéder à cette fonctionnalité.',
                        'plan': subscription.plan,
                        'required_plans': allowed_plans
                    },
                    status=403,
                    json_dumps_params={'ensure_ascii': False}
                )

            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator

# ---------------- require_quota ----------------
def require_quota(action_type):
    """
    usage: @require_quota('api') ou @require_quota('device')
    Les superusers ne sont pas limités par les quotas.
    """
    def _decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)

            ok, plan, usage, limits = check_quota(request.user, action_type)
            if not ok:
                return JsonResponse(
                    {
                        "error": "Quota dépassé pour votre plan.",
                        "plan": plan,
                        "required": limits,
                        "usage_today": {
                            "api_calls": usage.api_calls,
                            "device_count": usage.device_count
                        }
                    },
                    status=403,
                    json_dumps_params={'ensure_ascii': False}
                )

            increment_usage(request.user, action_type)
            return view_func(request, *args, **kwargs)
        return _wrapped
    return _decorator

# ---------------- premium_feature_required ----------------
def premium_feature_required(feature=None, required_plans=None):
    """
    Décorateur pour vérifier :
    - Le plan de l'utilisateur
    - Les quotas API et appareils
    - Les fonctionnalités premium selon le plan

    Les superusers ont toujours accès.
    """
    required_plans = required_plans or []

    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            user = request.user

            if not user.is_authenticated:
                return JsonResponse(
                    {'error': 'Utilisateur non authentifié.'},
                    status=403,
                    json_dumps_params={'ensure_ascii': False}
                )

            if user.is_superuser:
                return view_func(request, *args, **kwargs)

            limits = get_plan_limits(user)
            plan = user.subscription.plan if hasattr(user, 'subscription') else 'free'

            # Vérifier le plan autorisé
            if required_plans and plan not in required_plans:
                return JsonResponse(
                    {
                        "error": "Votre plan actuel ne permet pas d'accéder à cette fonctionnalité.",
                        "plan": plan,
                        "required_plans": required_plans
                    },
                    status=403,
                    json_dumps_params={'ensure_ascii': False}
                )

            # Vérifier quota API
            api_ok, usage_api, limit_api = check_api_quota(user)
            if not api_ok:
                return JsonResponse(
                    {
                        "error": "Quota API atteint pour votre plan.",
                        "usage": usage_api,
                        "limit": limit_api
                    },
                    status=403,
                    json_dumps_params={'ensure_ascii': False}
                )

            # Vérifier quota appareils
            dev_ok, usage_dev, limit_dev = check_device_quota(user)
            if not dev_ok:
                return JsonResponse(
                    {
                        "error": "Quota appareils atteints pour votre plan.",
                        "usage": usage_dev,
                        "limit": limit_dev
                    },
                    status=403,
                    json_dumps_params={'ensure_ascii': False}
                )

            # Vérifier fonctionnalité premium
            if feature and not limits.get(feature, False):
                return JsonResponse(
                    {
                        "error": f"Votre plan actuel ({plan}) ne permet pas d'utiliser la fonctionnalité : {feature}.",
                        "plan": plan,
                        "feature_required": feature
                    },
                    status=403,
                    json_dumps_params={'ensure_ascii': False}
                )

            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator
