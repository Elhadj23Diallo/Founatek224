from django.http import JsonResponse
from rest_framework.authentication import TokenAuthentication
from rest_framework.exceptions import AuthenticationFailed

EXEMPT_PATHS = ['/api/token-auth/', '/api/mobile/register/']

class APIKeyMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith('/api/') and request.path not in EXEMPT_PATHS:
            if not request.user.is_authenticated:
                try:
                    user_auth_tuple = TokenAuthentication().authenticate(request)
                    if user_auth_tuple is not None:
                        request.user, request.auth = user_auth_tuple
                    else:
                        return JsonResponse({'error': 'Token manquant ou invalide'}, status=403)
                except AuthenticationFailed:
                    return JsonResponse({'error': 'Échec d\'authentification par token'}, status=403)

        return self.get_response(request)
