from django.conf import settings
from django.http import JsonResponse
from rest_framework.authentication import TokenAuthentication
from rest_framework.exceptions import AuthenticationFailed

class APIKeyMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Vérification si l'utilisateur est un administrateur authentifié
        if request.user.is_authenticated and request.user.is_staff:
            # Si l'utilisateur est administrateur, il a accès à toutes les vues
            return self.get_response(request)

        # Si l'utilisateur est authentifié via un token
        if request.user.is_authenticated:
            try:
                # Tentative de récupération et validation du token
                TokenAuthentication().authenticate(request)
            except AuthenticationFailed:
                # Si le token est invalide ou absent, renvoyer une erreur 403
                return JsonResponse({'error': 'Token invalide ou manquant. Vous devez vous authentifier avant !'}, status=403)

        # Si aucune des conditions ci-dessus n'est remplie, continuer normalement
        return self.get_response(request)


# Vérification de permission d'accès API avec le token
def api_permission_required(view_func):
    def _wrapped_view(request, *args, **kwargs):
        # Vérification du token dans la requête
        if request.user.is_authenticated:
            try:
                # Authentifier l'utilisateur avec le token
                TokenAuthentication().authenticate(request)
            except AuthenticationFailed:
                # Si le token est invalide, renvoyer une erreur 403
                return JsonResponse({'error': 'Token invalide ou manquant. Vous devez vous authentifier avant !'}, status=403)

        # Accéder à la vue si toutes les conditions sont validées
        return view_func(request, *args, **kwargs)

    return _wrapped_view
