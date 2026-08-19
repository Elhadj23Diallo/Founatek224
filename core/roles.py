"""Determination centralisee du role d'un utilisateur (Formateur / Apprenant / Acheteur).

Le role ne donne JAMAIS acces a l'admin Django (is_staff) : c'est une simple
appartenance a un Group, utilisee uniquement pour filtrer la navigation.
"""

ROLE_FORMATEUR = "formateur"
ROLE_APPRENANT = "apprenant"
ROLE_ACHETEUR = "acheteur"


def get_user_role(user):
    if not user or not user.is_authenticated:
        return None
    # Un formateur "reel" a toujours un FormateurProfile (cree automatiquement
    # par le signal iot.signals quand on rejoint le groupe "Formateur").
    # Le staff/superuser voit aussi tout, comme un formateur (sans que ça leur
    # donne un role "Formateur" au sens metier — simple confort de navigation).
    if hasattr(user, "formateur_profile") or user.is_staff or user.is_superuser:
        return ROLE_FORMATEUR
    if user.groups.filter(name="Acheteur").exists():
        return ROLE_ACHETEUR
    if user.groups.filter(name="Apprenant").exists():
        return ROLE_APPRENANT
    return None


def role_context(user):
    role = get_user_role(user)
    return {
        "user_role": role,
        "is_formateur_role": role == ROLE_FORMATEUR,
        "is_apprenant_role": role == ROLE_APPRENANT,
        "is_acheteur_role": role == ROLE_ACHETEUR,
    }
