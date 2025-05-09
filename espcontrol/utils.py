# monappli/decorators.py
from django.http import JsonResponse
from django.conf import settings
from django.contrib.auth.decorators import login_required
from rest_framework.authentication import TokenAuthentication
from rest_framework.exceptions import AuthenticationFailed
# Vérification de permission d'accès API avec le token
def api_permission_required(view_func):
    def _wrapped_view(request, *args, **kwargs):
        print(f"Request headers: {request.headers}")  # Pour voir les en-têtes
        if request.user.is_authenticated:
            try:
                TokenAuthentication().authenticate(request)
            except AuthenticationFailed:
                return JsonResponse({'error': 'Token invalide ou manquant. Vous devez vous authentifier avant !'}, status=403)

        return view_func(request, *args, **kwargs)

    return _wrapped_view
