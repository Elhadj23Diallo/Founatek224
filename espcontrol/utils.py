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
