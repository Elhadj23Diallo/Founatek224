"""Protection CSRF pour les vues appelées à la fois par des appareils et par le site.

Les ESP32, scripts et l'appli mobile s'authentifient par jeton d'API
(APIKeyMiddleware pose ``request.authenticated_via_token = True``) : ils n'ont
pas de cookie CSRF, donc la vérification ne s'applique pas à eux. Un navigateur
connecté par cookie de session doit, lui, envoyer le jeton CSRF : sinon un autre
site pourrait déclencher l'action à sa place (commande d'un relais, etc.).
"""
from functools import wraps

from django.middleware.csrf import CsrfViewMiddleware
from django.views.decorators.csrf import csrf_exempt


def _csrf_reject_reason(request):
    """Rejoue la vérification CSRF de Django ; renvoie une réponse 403 ou None."""
    middleware = CsrfViewMiddleware(lambda req: None)
    middleware.process_request(request)
    return middleware.process_view(request, None, (), {})


def csrf_exempt_for_token(view_func):
    """Exempte du CSRF les appels authentifiés par jeton d'API uniquement."""

    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        if not getattr(request, "authenticated_via_token", False):
            response = _csrf_reject_reason(request)
            if response is not None:
                return response
        return view_func(request, *args, **kwargs)

    return csrf_exempt(wrapped)
