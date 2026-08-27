"""Lecture (avec cache) de la visibilité des modules Founatek, pilotée depuis
l'admin Django (iot.PlatformModule). Un module non encore créé en base est
considéré publié par défaut — un module désactivé par erreur d'oubli ne doit
jamais se retrouver caché sans action explicite de l'admin."""

from django.core.cache import cache

CACHE_KEY = "published_modules"
CACHE_TIMEOUT = 30  # secondes — décoché/coché dans l'admin visible sous 30s partout

# Clés reconnues côté site (menu_page.html) et mobile (HomeScreen). Un module
# manquant dans cette liste par défaut à True (voir docstring ci-dessus).
DEFAULT_MODULES = {
    "boutique": "Boutique",
    "tracabilite": "Traçabilité",
    "apprentissage": "Apprentissage",
    "social_feed": "Social Feed",
    "premium": "Premium / Monétisation",
    "caisse": "Scan Panier (Caisse)",
    # Sections du dashboard IoT (home.html)
    "air_quality": "Air Quality IoT",
    "actionneurs": "Actionneurs (Relais)",
    "capteurs": "Capteurs",
    "eclairage": "Éclairage (LED)",
    "surveillance_acces": "Sécurité & Surveillance",
    "analytics_export": "Analytics & Export",
}


def get_published_modules():
    cached = cache.get(CACHE_KEY)
    if cached is not None:
        return cached

    from iot.models import PlatformModule
    data = {key: True for key in DEFAULT_MODULES}
    data.update({m.key: m.is_published for m in PlatformModule.objects.all()})

    cache.set(CACHE_KEY, data, CACHE_TIMEOUT)
    return data
