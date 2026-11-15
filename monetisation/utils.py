from django.utils import timezone
from .models import Subscription, UsageLog
from datetime import timedelta

# ------------------------------
# ⚡ Conversion GNF <-> EUR (le wallet est stocke en EUR en interne pour PayPal,
# mais le Mobile Money en Guinee se paie naturellement en GNF)
# ------------------------------
DEFAULT_GNF_PER_EUR = 10000  # taux de secours si non configure dans ExchangeRate (founatekapp)


def get_gnf_to_eur_rate():
    """Retourne le taux de conversion 1 GNF -> X EUR (utilise ExchangeRate 'EUR' de founatekapp si dispo)."""
    try:
        from founatekapp.models import ExchangeRate
        rate = ExchangeRate.objects.filter(currency_code='EUR').first()
        if rate:
            return float(rate.rate_from_gnf)
    except Exception:
        pass
    return 1 / DEFAULT_GNF_PER_EUR


def gnf_to_eur(amount_gnf):
    return round(float(amount_gnf) * get_gnf_to_eur_rate(), 4)

# ------------------------------
# ⚡ Prix des abonnements — source unique (web ET mobile importent ce dict,
# pour ne jamais avoir deux prix differents pour le meme plan).
# ------------------------------
PLAN_PRICES = {
    'free': 0,
    'basic': 3,
    'pro': 15,
}

# Recharge wallet via PayPal : fourchette anti-abus (pas de minimum "metier",
# juste pour eviter les montants absurdes/negatifs/a 10 decimales).
CREDIT_TOPUP_MIN_EUR = 1
CREDIT_TOPUP_MAX_EUR = 500


def round_money(value):
    """Arrondit un montant en euros a 2 decimales (toujours utiliser cette
    fonction plutot qu'un round() a la main, pour rester coherent partout)."""
    return round(float(value), 2)


def validate_paypal_order_params(payment_type, plan, raw_amount):
    """Calcule le montant REEL a facturer pour un ordre PayPal, sans jamais
    faire confiance au montant envoye par le client.

    - type="subscription" : le montant est TOUJOURS PLAN_PRICES[plan], quoi
      que le client ait envoye (corrige la faille "abonnement Pro a 1 centime").
    - type="credit" : le montant vient du client mais doit rester dans
      [CREDIT_TOPUP_MIN_EUR, CREDIT_TOPUP_MAX_EUR].

    Retourne (amount, plan) ou leve ValueError(message utilisateur) si invalide.
    """
    if payment_type == "subscription":
        if not plan or plan not in PLAN_PRICES or plan == "free":
            raise ValueError("Plan d'abonnement invalide.")
        return round_money(PLAN_PRICES[plan]), plan

    if payment_type == "credit":
        try:
            amount = round_money(raw_amount)
        except (TypeError, ValueError):
            raise ValueError("Montant invalide.")
        if not (CREDIT_TOPUP_MIN_EUR <= amount <= CREDIT_TOPUP_MAX_EUR):
            raise ValueError(
                f"Le montant doit etre entre {CREDIT_TOPUP_MIN_EUR} et {CREDIT_TOPUP_MAX_EUR} EUR."
            )
        return amount, ""

    raise ValueError("Type de paiement invalide.")


def verify_paypal_capture(result, expected_user_id):
    """Verifie la reponse de capture PayPal renvoyee par PayPal lui-meme et en
    extrait (payment_type, plan, captured_amount) ou leve ValueError(message).

    Controles :
    - status == COMPLETED
    - devise == EUR
    - le custom_id porte bien l'id de l'utilisateur qui essaie de capturer
      (empeche de capturer/crediter la commande de quelqu'un d'autre)
    - pour un abonnement, le montant capture couvre au moins PLAN_PRICES[plan]
    """
    if result.get("status") != "COMPLETED":
        raise ValueError("Paiement non complete.")

    try:
        purchase_unit = result["purchase_units"][0]
        capture = purchase_unit["payments"]["captures"][0]
        currency = capture["amount"]["currency_code"]
        captured_amount = round_money(capture["amount"]["value"])
    except (KeyError, IndexError, TypeError, ValueError):
        raise ValueError("Reponse PayPal inattendue.")

    if currency != "EUR":
        raise ValueError("Devise inattendue.")

    custom_id = purchase_unit.get("custom_id", "")
    parts = custom_id.split("|")
    payment_type = parts[0] if parts else "credit"
    plan = parts[1] if len(parts) > 1 else ""
    custom_user_id = parts[2] if len(parts) > 2 else ""

    if custom_user_id != str(expected_user_id):
        raise ValueError("Cette commande n'appartient pas a cet utilisateur.")

    if payment_type == "subscription":
        if plan not in PLAN_PRICES or plan == "free":
            raise ValueError("Plan invalide.")
        if captured_amount < PLAN_PRICES[plan]:
            raise ValueError("Montant paye insuffisant pour ce plan.")

    return payment_type, plan, captured_amount


# ------------------------------
# ⚡ Définition des limites par plan
# ------------------------------
PLAN_LIMITS = {
    'free': {
        'calls': 100,
        'devices': 1,
        'history_days': 1,
        'alerts': True,
        'pdf_reports': False,
    },
    'basic': {
        'calls': 1000,
        'devices': 3,
        'history_days': 7,
        'alerts': True,
        'pdf_reports': True,
    },
    'pro': {
        'calls': 10000,
        'devices': 10,
        'history_days': 30,
        'alerts': True,
        'pdf_reports': True,
    },
}


# ------------------------------
# ⚡ Récupère les limites du plan de l'utilisateur
# ------------------------------
def get_plan_limits(user):
    sub = Subscription.objects.filter(user=user).first()
    if not sub:
        return PLAN_LIMITS['free']

    plan = sub.plan
    return PLAN_LIMITS.get(plan, PLAN_LIMITS['free'])


# ------------------------------
# ⚡ Vérifie quota API pour la journée
# ------------------------------
def check_api_quota(user):
    limits = get_plan_limits(user)
    max_calls = limits['calls']

    today = timezone.now().date()
    usage, _ = UsageLog.objects.get_or_create(user=user, date=today)

    ok = usage.api_calls < max_calls

    return ok, usage.api_calls, max_calls



# ------------------------------
# ⚡ Vérifie quota appareils
# ------------------------------
# monetisation/utils.py

from espcontrol.models import Device

# ------------------------------
# ⚡ Vérifie quota appareils
# ------------------------------
def check_device_quota(user):
    """
    Vérifie si l'utilisateur a atteint la limite d'appareils ESP32 (Device)
    autorisés par son plan.
    Retourne :
        ok (bool): True si quota pas atteint
        device_count (int): nombre actuel de devices
        max_devices (int): nombre maximal autorisé
    """
    limits = get_plan_limits(user)
    max_devices = limits['devices']

    device_count = Device.objects.filter(user=user).count()

    ok = device_count < max_devices
    return ok, device_count, max_devices