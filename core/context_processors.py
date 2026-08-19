from django.conf import settings
from .roles import role_context

def paypal_settings(request):
    return {
        "PAYPAL_CLIENT_ID": settings.PAYPAL_CLIENT_ID
    }


def user_role(request):
    return role_context(getattr(request, "user", None))
