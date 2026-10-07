from django.utils import translation


class UserLanguageMiddleware:
    """Applique la langue enregistree dans le profil de l'utilisateur connecte
    a CHAQUE requete web (apres AuthenticationMiddleware, pour avoir
    request.user) — c'est ce qui garantit que 'toute la plateforme' reste
    dans la langue choisie, meme sur un nouvel appareil/navigateur, sans
    dependre d'un cookie ou d'une session a reconfigurer a chaque fois.

    Ne concerne pas l'API mobile (authentification par token, resolue plus
    tard par DRF — request.user n'est pas encore disponible ici) : le client
    mobile envoie son propre en-tete Accept-Language, deja gere nativement
    par LocaleMiddleware."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if getattr(request, "user", None) and request.user.is_authenticated:
            lang = None
            try:
                lang = request.user.account_profile.language
            except Exception:
                lang = None
            if lang:
                translation.activate(lang)
                request.LANGUAGE_CODE = lang
        return self.get_response(request)
