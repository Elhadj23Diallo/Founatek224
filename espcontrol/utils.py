# monappli/decorators.py
from django.http import JsonResponse
from django.conf import settings
from django.contrib.auth.decorators import login_required
from rest_framework.authentication import TokenAuthentication
from rest_framework.exceptions import AuthenticationFailed
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
