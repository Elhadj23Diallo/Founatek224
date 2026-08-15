from django.http import JsonResponse
from rest_framework.authentication import TokenAuthentication
from rest_framework.exceptions import AuthenticationFailed

class APIKeyMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Appliquer ce middleware uniquement aux routes qui commencent par '/api/'
        if request.path.startswith('/api/'):
            if not request.user.is_authenticated:
                try:
                    # Tentative de récupération et de validation du token
                    user_auth_tuple = TokenAuthentication().authenticate(request)
                    if user_auth_tuple is not None:
                        # Authentification réussie, on met à jour request.user
                        request.user, request.auth = user_auth_tuple
                    else:
                        return JsonResponse({'error': 'Token manquant ou invalide'}, status=403)
                except AuthenticationFailed:
                    return JsonResponse({'error': 'Échec d’authentification par token'}, status=403)

        return self.get_response(request)
