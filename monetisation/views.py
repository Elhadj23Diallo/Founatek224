from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.utils import timezone
from django.db import transaction
from datetime import timedelta
from .models import Wallet, Transaction, Subscription, PaymentRequest, Referral, ReferralTransaction
import logging
import uuid
import json
from .utils import (
    PLAN_LIMITS,
    PLAN_PRICES,
    round_money,
    award_referral_commission,
    convert_referral_points,
    paypal_capture_id,
    POINTS_PER_EURO,
    MIN_POINTS_TO_CONVERT,
    validate_paypal_order_params,
    verify_paypal_capture,
)
from .quota import IOT_LIMITS

#integration paypal
# monetisation/views.py
import requests
from django.conf import settings

logger = logging.getLogger(__name__)

@login_required
def create_paypal_order(request):
    """
    Crée un ordre PayPal pour l'achat de crédits ou le changement d'abonnement.
    JSON attendu :
    {
        "type": "credit" ou "subscription",
        "plan": "basic" (si type=subscription),
        "amount": 10 (si type=credit — ignoré pour un abonnement)
    }
    Le montant n'est JAMAIS pris tel quel depuis le client : pour un abonnement
    il est fixé par PLAN_PRICES, pour une recharge il est borné (anti-abus).
    """
    data = json.loads(request.body)
    payment_type = data.get("type", "credit")
    plan = data.get("plan")

    try:
        amount, plan = validate_paypal_order_params(payment_type, plan, data.get("amount"))
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    custom_id = f"{payment_type}|{plan}|{request.user.id}"

    # Créer l'ordre PayPal
    url = f"{settings.PAYPAL_API_BASE}/v2/checkout/orders"
    auth = (settings.PAYPAL_CLIENT_ID, settings.PAYPAL_SECRET)
    payload = {
        "intent": "CAPTURE",
        "purchase_units": [
            {
                "amount": {"currency_code": "EUR", "value": f"{amount:.2f}"},
                "custom_id": custom_id,
            }
        ]
    }

    try:
        response = requests.post(url, json=payload, auth=auth, timeout=20)
    except requests.RequestException:
        logger.exception("PayPal injoignable (création de commande, %s)", settings.PAYPAL_API_BASE)
        return JsonResponse({"error": "PayPal est injoignable, réessayez dans un instant."}, status=502)
    if response.status_code != 201:
        # La réponse de PayPal dit pourquoi (clés refusées, compte restreint...).
        logger.error(
            "PayPal a refusé la création de commande (%s, %s) : %s",
            response.status_code, settings.PAYPAL_API_BASE, response.text[:500],
        )
        return JsonResponse({"error": "Impossible de créer la commande PayPal"}, status=400)

    order = response.json()
    PaymentRequest.objects.create(
        user=request.user,
        provider='paypal',
        amount=amount,
        status='pending',
        transaction_id=order.get("id"),
    )
    return JsonResponse(order)


#📌 B. Capturer l’ordre PayPal et créditer le wallet

@login_required
def capture_paypal_order(request):
    data = json.loads(request.body)
    order_id = data.get("orderID")
    if not order_id:
        return JsonResponse({"error": "orderID requis"}, status=400)

    with transaction.atomic():
        try:
            payment = PaymentRequest.objects.select_for_update().get(
                transaction_id=order_id, provider='paypal'
            )
        except PaymentRequest.DoesNotExist:
            # Soit l'ordre n'existe pas, soit il n'a pas été créé par
            # create_paypal_order (donc jamais au bon prix) : on refuse.
            return JsonResponse({"error": "Commande inconnue"}, status=400)

        if payment.user_id != request.user.id:
            return JsonResponse({"error": "Cette commande n'appartient pas à cet utilisateur"}, status=403)

        if payment.status != 'pending':
            # Déjà traité (rejeu/double appel) : ne pas créditer une 2e fois.
            return JsonResponse({"success": True, "already_processed": True})

        url = f"{settings.PAYPAL_API_BASE}/v2/checkout/orders/{order_id}/capture"
        auth = (settings.PAYPAL_CLIENT_ID, settings.PAYPAL_SECRET)
        response = requests.post(url, auth=auth)
        result = response.json()

        try:
            payment_type, plan, captured_amount = verify_paypal_capture(result, request.user.id)
        except ValueError as exc:
            return JsonResponse({"success": False, "error": str(exc)}, status=400)

        wallet = Wallet.objects.select_for_update().get(user=request.user)

        if payment_type == "credit":
            wallet.balance = round_money(wallet.balance + captured_amount)
            wallet.save()
            Transaction.objects.create(
                user=request.user,
                type="credit",
                amount=captured_amount,
                description="Recharge via PayPal"
            )

        elif payment_type == "subscription" and plan:
            sub = Subscription.objects.select_for_update().get(user=request.user)
            sub.plan = plan
            sub.end_date = timezone.now().date() + timedelta(days=30)
            sub.save()
            Transaction.objects.create(
                user=request.user,
                type="subscription",
                amount=captured_amount,
                description=f"Abonnement {plan} via PayPal"
            )

        # ⚡ Attribution de la commission au parrain (points, pas wallet) —
        # seulement ici, APRÈS confirmation du paiement par PayPal lui-même.
        award_referral_commission(
            request.user, captured_amount,
            f"Commission sur {payment_type} de {request.user.username}",
            payment=payment,
        )

        payment.status = 'success'
        payment.purpose = payment_type
        # Capture PayPal : sert à retrouver ce paiement en cas de remboursement/litige
        payment.external_id = paypal_capture_id(result)
        payment.save()

    return JsonResponse({"success": True})


# ---------------- Dashboard ----------------
@login_required
@never_cache
def dashboard(request):
    from monetisation.quota import check_iot_quota
    from monetisation.utils import check_device_quota

    wallet = Wallet.objects.get(user=request.user)
    subscription = Subscription.objects.get(user=request.user)
    _, plan, iot_calls_used, max_iot_calls = check_iot_quota(request.user)
    _, device_count, max_devices = check_device_quota(request.user)

    return render(request, 'monetisation/dashboard.html', {
        'wallet': wallet,
        'subscription': subscription,
        'usage': {'iot_calls': iot_calls_used, 'device_count': device_count},
        'limits': {'iot_calls': max_iot_calls, 'devices': max_devices},
        'plan': plan,
        'currency': 'EUR'
    })


# ---------------- Historique des Transactions ----------------
@login_required
def transactions(request):
    tx = Transaction.objects.filter(user=request.user).order_by('-timestamp')
    return render(request, 'monetisation/transactions.html', {"transactions": tx})


# ---------------- Gestion Abonnement ----------------
# PLAN_PRICES importé depuis .utils (source unique, partagée avec espcontrol/api_views.py)

def _plans_info():
    return [
        {
            'name': plan_name,
            'calls': IOT_LIMITS[plan_name],
            'devices': limits['devices'],
            'history_days': limits['history_days'],
            'alerts': limits['alerts'],
            'pdf_reports': limits['pdf_reports'],
            'price': PLAN_PRICES[plan_name],
        }
        for plan_name, limits in PLAN_LIMITS.items()
    ]


def _render_subscription(request, sub, wallet, error=None):
    return render(request, 'monetisation/abonnement.html', {
        'subscription': sub,
        'plans': _plans_info(),
        'wallet': wallet,
        'stripe_enabled': settings.STRIPE_ENABLED,
        'error': error,
    })


@login_required
@never_cache
def subscription_view(request):
    sub = Subscription.objects.get(user=request.user)
    wallet = Wallet.objects.get(user=request.user)

    if request.method == 'POST':
        new_plan = request.POST.get('plan')
        provider = request.POST.get('provider')
        if new_plan not in PLAN_PRICES:
            return _render_subscription(request, sub, wallet, "Plan d'abonnement invalide.")
        amount = PLAN_PRICES[new_plan]

        # --- Plan gratuit ---
        if amount == 0:
            sub.plan = 'free'
            sub.end_date = None
            sub.save()
            Transaction.objects.create(
                user=request.user,
                type='debit',  # ou 'credit', selon ta logique
                amount=0,
                description="Changement vers plan gratuit"
            )
            return redirect('monetisation:payment_success')

        # --- Paiement via Wallet ---
        if provider == 'wallet':
            # Lignes verrouillées : un double clic ne débite pas deux fois.
            with transaction.atomic():
                wallet = Wallet.objects.select_for_update().get(user=request.user)
                sub = Subscription.objects.select_for_update().get(user=request.user)
                if wallet.balance < amount:
                    missing = round_money(amount - wallet.balance)
                    return _render_subscription(
                        request, sub, wallet,
                        f"Solde insuffisant : il vous manque {missing:.2f} €. Rechargez votre wallet ou payez avec PayPal."
                    )

                wallet.balance = round_money(wallet.balance - amount)
                wallet.save()

                sub.plan = new_plan
                sub.end_date = timezone.now().date() + timedelta(days=30)
                sub.save()

                Transaction.objects.create(
                    user=request.user,
                    type='debit',
                    amount=amount,
                    description=f"Abonnement {new_plan} payé avec Wallet"
                )
                PaymentRequest.objects.create(
                    user=request.user,
                    provider='wallet',
                    amount=amount,
                    status='success',
                    transaction_id=str(uuid.uuid4())
                )

            # ⚡ Pas de commission ici : payer un abonnement avec le solde du
            # wallet, c'est dépenser de l'argent déjà commissionné à la
            # recharge (admin, callback signé ou webhook Stripe) ou lors d'un
            # paiement PayPal direct d'abonnement. Une commission ici serait
            # une 2e commission sur le même argent.

            return redirect('monetisation:payment_success')

        # --- Provider non supporté pour l'abonnement (seuls wallet et paypal le sont) ---
        return _render_subscription(
            request, sub, wallet,
            "Ce moyen de paiement n'est pas disponible pour l'abonnement. Rechargez votre wallet puis payez avec le solde."
        )

    return _render_subscription(request, sub, wallet)
# ---------------- Dashboard Wallet ----------------
@login_required
@never_cache
def wallet_dashboard(request):
    from .stripe_payments import STRIPE_TOPUP_CHOICES_EUR
    wallet = Wallet.objects.get(user=request.user)
    payments = PaymentRequest.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'monetisation/wallet_dashboard.html', {
        'wallet': wallet,
        'payments': payments,
        'stripe_enabled': settings.STRIPE_ENABLED,
        'stripe_topup_choices': STRIPE_TOPUP_CHOICES_EUR,
    })


# ---------------- Initier Paiement Mobile Money ----------------
@login_required
def init_mobile_money(request):
    from .utils import gnf_to_eur, get_gnf_to_eur_rate
    from .models import MobileMoneyAccount
    from .stripe_payments import STRIPE_TOPUP_MIN_EUR, STRIPE_TOPUP_MAX_EUR
    wallet = Wallet.objects.get(user=request.user)
    # Option « Carte bancaire (Stripe) » : le paiement part en JavaScript vers
    # stripe_create_checkout, le formulaire n'est pas envoyé au serveur.
    card_ctx = {
        'stripe_enabled': settings.STRIPE_ENABLED,
        'stripe_min': STRIPE_TOPUP_MIN_EUR,
        'stripe_max': STRIPE_TOPUP_MAX_EUR,
    }
    # Venu de la page Abonnement (solde insuffisant) : montant pré-rempli et
    # retour vers l'abonnement après le paiement.
    return_to = request.GET.get('retour') if request.GET.get('retour') == 'abonnement' else ''
    try:
        prefill_amount = round_money(request.GET.get('montant')) if request.GET.get('montant') else None
    except (TypeError, ValueError):
        prefill_amount = None
    if prefill_amount is not None and not (0 < prefill_amount <= STRIPE_TOPUP_MAX_EUR):
        prefill_amount = None
    card_ctx.update({'return_to': return_to, 'prefill_amount': prefill_amount})

    if request.method == 'POST':
        provider = request.POST.get('provider') or ''
        phone_number = request.POST.get('phone_number', '')
        try:
            amount = float(request.POST.get('amount', 0))
        except (TypeError, ValueError):
            amount = 0

        # Vérification basique (la carte Stripe passe par stripe_create_checkout,
        # jamais par ce formulaire)
        if provider.lower() not in ('paypal', 'mtn', 'orange', 'moov', 'wave'):
            amount = 0
        if amount <= 0:
            return render(request, 'monetisation/init_mobile_money.html', {
                'wallet': wallet,
                'error': "Veuillez saisir un montant valide.",
                'merchant_accounts': MobileMoneyAccount.objects.filter(is_active=True),
                'gnf_to_eur_rate': get_gnf_to_eur_rate(),

                **card_ctx,
            })

        # PayPal facture directement en EUR. Le Mobile Money guineen se paie en GNF :
        # on convertit vers EUR (devise interne du wallet) pour rester coherent.
        if provider.lower() == 'paypal':
            amount_eur = round_money(amount)
            amount_local = None
            currency_local = 'EUR'
        else:
            amount_local = amount
            currency_local = 'GNF'
            amount_eur = round_money(gnf_to_eur(amount))

        # Créer un PaymentRequest
        payment = PaymentRequest.objects.create(
            user=request.user,
            provider=provider,
            phone_number=phone_number,
            amount=amount_eur,
            amount_local=amount_local,
            currency_local=currency_local,
            transaction_id=str(uuid.uuid4()),
            status='pending'
        )

        # Pour PayPal, rediriger vers le dashboard et laisser le front gérer l'ordre
        if provider.lower() == 'paypal':
            return redirect('monetisation:wallet_dashboard')

        # Pour Mobile Money, le paiement est manuel (envoi vers un numero marchand) :
        # la demande reste 'pending' jusqu'a confirmation par un admin (email envoye automatiquement).
        return redirect('monetisation:wallet_dashboard')

    return render(request, 'monetisation/init_mobile_money.html', {
        'wallet': wallet,
        'currency': 'EUR',
        'merchant_accounts': MobileMoneyAccount.objects.filter(is_active=True),
        'gnf_to_eur_rate': get_gnf_to_eur_rate(),
        **card_ctx,
    })


# ---------------- Callback Mobile Money ----------------
# ⚠️ Route volontairement désactivée (faille de sécurité) : aucun opérateur
# Mobile Money n'appelle réellement cette URL aujourd'hui (voir le commentaire
# sur MobileMoneyAccount dans models.py — pas d'API opérateur, paiement manuel
# vers un numéro marchand). Elle était en @csrf_exempt, hors de /api/ (donc pas
# protégée par APIKeyMiddleware) et sans aucune vérification de signature :
# n'importe qui pouvait POSTer {"transaction_id": ..., "status": "SUCCESS"} sur
# une demande 'pending' pour créditer le wallet et payer la commission du
# parrain sans jamais payer. La validation des recharges Mobile Money reste
# manuelle, via mobile_monetisation_admin_review (staff only, espcontrol/api_views.py).
# Si un opérateur fournit un jour un vrai callback, le réintroduire avec une
# signature HMAC vérifiée (hmac.compare_digest) sur un secret d'environnement.


from monetisation.quota import get_limits_for_user
from monetisation.models import UsageLog
from django.utils import timezone


@login_required
def referral_dashboard(request):
    user = request.user

    # Code de parrainage
    try:
        my_referral = Referral.objects.get(referred=user)
        referral_code = my_referral.code
    except Referral.DoesNotExist:
        referral_code = None

    # Liste des filleuls
    referrals = Referral.objects.filter(referrer=user)

    # Toutes les commissions (converties ou non) pour l'affichage dans le tableau
    commissions = ReferralTransaction.objects.filter(referral__referrer=user).order_by('-created_at')

    # Total uniquement des commissions NON converties
    total_commissions = round(sum(c.amount for c in commissions if not c.converted), 2)

    return render(request, 'monetisation/referrals.html', {
        'referral_code': referral_code,
        'referrals': referrals,
        'commissions': commissions,           # Affichage complet
        'total_commissions': total_commissions,  # Total non converti
        'total_commissions_eur': total_commissions / POINTS_PER_EURO,
        'MIN_POINTS_TO_CONVERT': MIN_POINTS_TO_CONVERT,
    })





@login_required
def wallet_paypal_checkout(request):
    from django.conf import settings
    import requests
    from django.http import JsonResponse

    payment_id = request.session.get('wallet_payment_id')
    if not payment_id:
        return redirect('monetisation:subscription_view')

    payment = PaymentRequest.objects.get(id=payment_id)
    amount = payment.amount

    # Créer ordre PayPal pour ton compte développeur
    url = f"{settings.PAYPAL_API_BASE}/v2/checkout/orders"
    auth = (settings.PAYPAL_CLIENT_ID, settings.PAYPAL_SECRET)
    payload = {
        "intent": "CAPTURE",
        "purchase_units": [
            {
                "amount": {"currency_code": "EUR", "value": str(amount)},
                "custom_id": f"wallet_payment|{payment.id}"
            }
        ]
    }
    response = requests.post(url, json=payload, auth=auth)
    if response.status_code == 201:
        order_id = response.json()['id']
        return render(request, 'monetisation/wallet_paypal.html', {
            'order_id': order_id,
            'amount': amount
        })
    else:
        return render(request, 'monetisation/wallet_paypal.html', {
            'order_id': None,
            'amount': payment.amount,
            'error': "Impossible de créer la commande PayPal"
        })


from django.contrib import messages


@login_required
def convert_commission_to_wallet(request):
    if request.method != 'POST':
        return redirect('monetisation:referral_dashboard')
    try:
        points, euros = convert_referral_points(request.user)
    except ValueError as exc:
        messages.error(request, str(exc))
        return redirect('monetisation:referral_dashboard')

    messages.success(
        request,
        f"Vous avez converti {points:g} points en {euros:.2f} € dans votre Wallet !"
    )
    return redirect('monetisation:wallet_dashboard')

@login_required
def payment_success(request):
    return render(request, "monetisation/payment_success.html")

