"""Filtre des rapports d'erreur envoyés par e-mail à l'administrateur.

En plus de ce que Django masque déjà (clés, mots de passe, en-tête
Authorization, cookie de session), on masque le jeton CSRF et tout champ de
formulaire dont le nom évoque un secret (mot de passe, jeton, carte…).
"""
import re

from django.views.debug import SafeExceptionReporterFilter


class SensitiveDataFilter(SafeExceptionReporterFilter):
    hidden_settings = re.compile(
        "API|AUTH|TOKEN|KEY|SECRET|PASS|SIGNATURE|COOKIE|CSRF|SESSION|CARD|IBAN", flags=re.I
    )

    def get_post_parameters(self, request):
        params = super().get_post_parameters(request)
        if request is None or not self.is_active(request):
            return params
        cleansed = params.copy()
        for key in list(cleansed.keys()):
            if self.hidden_settings.search(key):
                cleansed[key] = self.cleansed_substitute
        return cleansed
