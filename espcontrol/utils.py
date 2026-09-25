# monappli/decorators.py
from django.http import JsonResponse
from django.conf import settings
from django.contrib.auth.decorators import login_required
from rest_framework.authentication import TokenAuthentication
from rest_framework.exceptions import AuthenticationFailed
# Vérification de permission d'accès API avec le token
def api_permission_required(view_func):
    def _wrapped_view(request, *args, **kwargs):
        print(f"Request headers: {request.headers}")  # Pour voir les en-têtes
        if request.user.is_authenticated:
            try:
                TokenAuthentication().authenticate(request)
            except AuthenticationFailed:
                return JsonResponse({'error': 'Token invalide ou manquant. Vous devez vous authentifier avant !'}, status=403)

        return view_func(request, *args, **kwargs)

    return _wrapped_view


# utils.py
import re
from difflib import get_close_matches

ARTICLES = r"\b(la|le|les|du|de|des|un|une|au|aux|mon|ma|mes|ton|ta|tes|son|sa|ses|dans|sur|à|a|en)\b"

def normalize(txt: str) -> str:
    txt = txt.lower()
    txt = re.sub(ARTICLES, " ", txt)
    txt = re.sub(r"[^\w\s]", " ", txt)
    txt = re.sub(r"\s+", " ", txt)
    return txt.strip()

def fuzzy_in(needle, haystack_set, cutoff=0.7):
    match = get_close_matches(needle, haystack_set, n=1, cutoff=cutoff)
    return match[0] if match else None

def extract_rgb(text):
    m = re.search(r"rgb\s*\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})\s*\)", text)
    if m:
        return tuple(max(0, min(255, int(x))) for x in m.groups())

    colors = {
        "rouge": (255, 0, 0),
        "vert": (0, 255, 0),
        "bleu": (0, 0, 255),
        "jaune": (255, 255, 0),
        "violet": (128, 0, 128),
        "rose": (255, 105, 180),
        "blanc": (255, 255, 255),
        "orange": (255, 165, 0),
        "cyan": (0, 255, 255),
    }

    for name, rgb in colors.items():
        if name in text:
            return rgb
    return None


def get_air_quality_color(user, window=3):
    """Couleur de veilleuse (r, g, b) a partir de la MEDIANE des dernieres
    lectures PM2.5 de l'utilisateur (pas juste la toute derniere) — vert si
    bon, jaune si modere, rouge si mauvais/tres mauvais. Blanc neutre si
    aucune donnee recente (pas d'alerte fausse).

    La mediane (pas une simple moyenne) ignore un pic isole (capteur
    bruyant, faux positif/negatif ponctuel) : sur une fenetre de 3, une
    seule valeur aberrante n'influence jamais le resultat, alors qu'une
    moyenne se laisse encore tirer par une valeur extreme. Un vrai
    changement soutenu (2 lectures sur 3 dans la nouvelle categorie) est en
    revanche bien detecte."""
    from statistics import median
    from . import who_air
    from .models import Device, AppareilData

    device = Device.objects.filter(user=user, is_active=True).order_by("-last_seen").first()
    if not device:
        return (255, 255, 255)

    readings = AppareilData.objects.filter(device=device).order_by("-received_at")[:window]
    values = [
        r.payload.get("pm2p5") for r in readings
        if r.payload and isinstance(r.payload.get("pm2p5"), (int, float))
    ]
    if not values:
        return (255, 255, 255)
    pm25 = median(values)

    # Niveaux OMS (espcontrol/who_air.py) : Excellent/Bon -> vert,
    # Modere/Mediocre -> jaune, Mauvais/Dangereux -> rouge.
    idx = who_air.level_index("pm2p5", pm25)
    if idx <= 1:
        return (0, 255, 0)
    if idx <= 3:
        return (255, 255, 0)
    return (255, 0, 0)
