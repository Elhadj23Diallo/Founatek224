"""Renonciation au droit de rétractation pour les contenus numériques.

Pour un contenu numérique fourni tout de suite (pack Livre 1, parcours), le
droit de rétractation de 14 jours ne s'applique pas si le client a donné son
accord exprès pour l'accès immédiat et renoncé expressément à ce droit
(article L221-28, 13° du Code de la consommation). Le site demande donc de
cocher une case avant tout paiement, la vérifie côté serveur et garde la date
de l'accord sur le paiement (et dans les métadonnées Stripe).
"""
import json

WAIVER_FIELD = "accept_conditions"

WAIVER_ERROR = (
    "Coche la case : tu acceptes les CGV, tu demandes l'accès immédiat au contenu "
    "et tu renonces à ton droit de rétractation."
)

# Rappel affiché par Stripe sous le bouton de paiement.
STRIPE_SUBMIT_MESSAGE = (
    "Contenu numérique : accès immédiat après paiement. Vous avez accepté les CGV "
    "et renoncé à votre droit de rétractation."
)

_TRUE_VALUES = {"1", "true", "on", "yes", "oui"}


def _truthy(value):
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in _TRUE_VALUES


def waiver_from_request(request):
    """True si la case a été cochée (formulaire, JSON ou requête DRF)."""
    data = getattr(request, "data", None)  # requête Django REST Framework
    if data is not None and hasattr(data, "get") and data.get(WAIVER_FIELD) is not None:
        return _truthy(data.get(WAIVER_FIELD))
    if request.POST.get(WAIVER_FIELD) is not None:
        return _truthy(request.POST.get(WAIVER_FIELD))
    if (request.content_type or "").startswith("application/json"):
        try:
            body = json.loads(request.body or b"{}")
        except ValueError:
            return False
        if isinstance(body, dict):
            return _truthy(body.get(WAIVER_FIELD))
    return False
