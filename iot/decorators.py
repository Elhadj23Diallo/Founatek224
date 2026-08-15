from django.contrib.auth.decorators import user_passes_test
from django.core.exceptions import PermissionDenied
from functools import wraps


# ============================
# 👨‍🏫 Rôle Formateur / Admin
# ============================
def is_formateur(user):
    return (
        user.is_authenticated
        and (
            user.is_superuser
            or user.is_staff
            or user.groups.filter(name="Administrateur").exists()
        )
    )


formateur_required = user_passes_test(
    is_formateur,
    login_url="login",
    redirect_field_name=None
)


# ============================
# 🏢 Organisation requise
# ============================
def organisation_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):

        # Superuser → autorisé partout
        if request.user.is_superuser:
            return view_func(request, *args, **kwargs)

        # Pas de profil formateur
        if not hasattr(request.user, "formateur_profile"):
            raise PermissionDenied(
                "Vous n’êtes rattaché à aucune organisation."
            )

        return view_func(request, *args, **kwargs)

    return wrapper
