# monappli/decorators.py
from django.http import JsonResponse
from django.conf import settings
from django.contrib.auth.decorators import login_required
def api_permission_required(view_func):
    def _wrapped_view(request, *args, **kwargs):
        # Si l'utilisateur est connecté ET est admin, accès autorisé sans clé
        if request.user.is_authenticated and request.user.is_staff:
            return view_func(request, *args, **kwargs)

        # Sinon, vérifier la clé API dans la requête
        key = request.GET.get('secret_key') or request.POST.get('secret_key')
        if key != settings.API_SECRET_KEY:
            return JsonResponse({'error': 'Clé API invalide ou manquante'}, status=403)

        return view_func(request, *args, **kwargs)

    return _wrapped_view
