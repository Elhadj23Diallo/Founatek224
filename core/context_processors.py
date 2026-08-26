from django.conf import settings
from .roles import role_context
from .module_visibility import get_published_modules

def paypal_settings(request):
    return {
        "PAYPAL_CLIENT_ID": settings.PAYPAL_CLIENT_ID
    }


def user_role(request):
    return role_context(getattr(request, "user", None))


def published_modules(request):
    return {"published_modules": get_published_modules()}
