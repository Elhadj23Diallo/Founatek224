from django.http import JsonResponse

# API "matériel" : appelées par les ESP32/appareils eux-mêmes, pas par un
# humain qui navigue sur le site/l'app. Seules celles-ci comptent contre le
# quota IoT — les autres endpoints /api/mobile/* (monetisation, chatbot,
# éducation...) ne sont pas concernés.
IOT_API_PREFIXES = (
    '/api/iot/ingest/',
    '/api/sensor/',
    '/api/sensor_ntc/',
    '/api/compteur/',
    '/api/relais/',
    '/api/led/',
    '/api/led_color/',
    '/api/check_access/',
    '/api/upload/',
)


class IoTQuotaMiddleware:
    """Doit être placé APRÈS APIKeyMiddleware dans MIDDLEWARE : s'appuie sur
    request.authenticated_via_token, posé par celui-ci."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith(IOT_API_PREFIXES):
            if getattr(request, 'authenticated_via_token', False):
                from monetisation.quota import check_iot_quota, increment_iot_usage

                ok, plan, used, limit = check_iot_quota(request.user)
                if not ok:
                    return JsonResponse(
                        {
                            'error': 'Quota IoT atteint, remise à zéro à minuit.',
                            'plan': plan,
                            'used_today': used,
                            'limit': limit,
                        },
                        status=429,
                    )
                increment_iot_usage(request.user)
            elif request.user.is_authenticated:
                # Appel par session web (humain) : pas de quota journalier,
                # mais un garde-fou de débit pour éviter qu'un script
                # authentifié par session ne martèle ces routes matériel.
                from monetisation.quota import check_session_rate_limit, SESSION_RATE_LIMIT_PER_MINUTE

                ok, count = check_session_rate_limit(request.user)
                if not ok:
                    return JsonResponse(
                        {
                            'error': 'Trop de requêtes, réessaie dans une minute.',
                            'limit_per_minute': SESSION_RATE_LIMIT_PER_MINUTE,
                        },
                        status=429,
                    )

        return self.get_response(request)
