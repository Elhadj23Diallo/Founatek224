# monappli/middleware/api_key_middleware.py
from django.conf import settings
from django.http import JsonResponse
from django.contrib.auth.models import Permission

class APIKeyMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Vérifier si l'utilisateur est authentifié et est un administrateur
        if request.user.is_authenticated and request.user.is_staff:
            # Si l'utilisateur est un admin connecté, il a accès à toutes les vues
            return self.get_response(request)

        # Si l'utilisateur n'est pas connecté mais demande une API, vérifier la clé API
        if request.path.startswith('/api/'):
            key = request.POST.get('secret_key') or request.GET.get('secret_key')
            if key != settings.API_SECRET_KEY:
                # Si la clé API est incorrecte ou manquante, renvoyer une erreur 403
                return JsonResponse({'error': 'Clé API invalide ou manquante'}, status=403)

        # Si aucune des conditions ci-dessus n'est remplie, continuer normalement
        return self.get_response(request)


def api_permission_required(view_func):
    def _wrapped_view(request, *args, **kwargs):
        # Vérifier la clé API dans la requête
        key = request.GET.get('secret_key') or request.POST.get('secret_key')
        if key != settings.API_SECRET_KEY:
            return JsonResponse({'error': 'Clé API invalide ou manquante'}, status=403)
        return view_func(request, *args, **kwargs)
    return _wrapped_view