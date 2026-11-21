"""Pages légales : mentions légales, CGV, politique de confidentialité.

Les informations de l'éditeur (adresse, SIRET…) viennent du .env (variables
LEGAL_*) pour ne pas être écrites dans le dépôt public. Tant qu'une valeur
manque, la page affiche « [à compléter] » et le superutilisateur voit la liste
des variables à remplir.
"""
import os

from django.shortcuts import render

LEGAL_FIELDS = [
    # (clé, variable .env, valeur par défaut, libellé pour l'admin)
    ("name", "LEGAL_NAME", "FOUNATEK", "nom commercial"),
    ("owner", "LEGAL_OWNER", "", "nom et prénom du responsable (directeur de la publication)"),
    ("form", "LEGAL_FORM", "", "forme juridique (ex. entreprise individuelle / micro-entreprise)"),
    ("address", "LEGAL_ADDRESS", "", "adresse postale"),
    ("siret", "LEGAL_SIRET", "", "numéro SIRET"),
    ("vat", "LEGAL_VAT", "", "TVA : numéro intracommunautaire, ou « TVA non applicable, art. 293 B du CGI »"),
    ("email", "LEGAL_EMAIL", "", "adresse e-mail de contact"),
    ("phone", "LEGAL_PHONE", "", "téléphone (facultatif mais recommandé)"),
    ("mediator", "LEGAL_MEDIATOR", "", "médiateur de la consommation (nom et site web)"),
]

HOST = {
    "name": "PythonAnywhere LLP",
    "address": "5 The Green, Richmond TW9 1PL, Royaume-Uni",
    "website": "https://www.pythonanywhere.com",
}

LAST_UPDATE = "21 novembre 2026"
PLACEHOLDER = "[à compléter]"


def legal_info():
    info, missing = {}, []
    for key, env, default, label in LEGAL_FIELDS:
        value = os.getenv(env, default).strip()
        if not value:
            missing.append((env, label))
            value = PLACEHOLDER
        info[key] = value
    return info, missing


def _render(request, template):
    info, missing = legal_info()
    show_missing = bool(request.user.is_authenticated and request.user.is_superuser and missing)
    return render(request, template, {
        "legal": info,
        "host": HOST,
        "last_update": LAST_UPDATE,
        "missing": missing if show_missing else [],
    })


def mentions_legales(request):
    return _render(request, "legal/mentions_legales.html")


def cgv(request):
    return _render(request, "legal/cgv.html")


def confidentialite(request):
    return _render(request, "legal/confidentialite.html")
