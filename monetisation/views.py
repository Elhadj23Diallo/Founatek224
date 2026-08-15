from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.utils import timezone
from .models import Wallet, Transaction, Subscription, PaymentRequest, Referral, ReferralTransaction
import uuid
import json
from .utils import PLAN_LIMITS

#integration paypal
# monetisation/views.py
import requests
from django.conf import settings

@login_required
def create_paypal_order(request):
    """
    Crée un ordre PayPal pour l'achat de crédits ou le changement d'abonnement.
    JSON attendu :
    {
        "amount": 10,
        "type": "credit" ou "subscription",
        "plan": "basic" (si type=subscription)
    }
    """
    data = json.loads(request.body)
    amount = data.get("amount")
    payment_type = data.get("type", "credit")
    plan = data.get("plan")  # facultatif, pour abonnement

    # Créer l'ordre PayPal
    url = f"{settings.PAYPAL_API_BASE}/v2/checkout/orders"
    auth = (settings.PAYPAL_CLIENT_ID, settings.PAYPAL_SECRET)
    payload = {
        "intent": "CAPTURE",
        "purchase_units": [
            {
                "amount": {"currency_code": "EUR", "value": str(amount)},
                "custom_id": f"{payment_type}|{plan or ''}"  # stocke info type/plan
            }
        ]
    }

    response = requests.post(url, json=payload, auth=auth)
    if response.status_code == 201:
        return JsonResponse(response.json())
    return JsonResponse({"error": "Impossible de créer la commande PayPal"}, status=400)


#📌 B. Capturer l’ordre PayPal et créditer le walle
from .models import Wallet, Transaction

@login_required
def capture_paypal_order(request):
    data = json.loads(request.body)
    order_id = data.get("orderID")

    url = f"{settings.PAYPAL_API_BASE}/v2/checkout/orders/{order_id}/capture"
    auth = (settings.PAYPAL_CLIENT_ID, settings.PAYPAL_SECRET)
    response = requests.post(url, auth=auth)
    result = response.json()

    if result.get("status") != "COMPLETED":
        return JsonResponse({"success": False, "error": "Paiement non complété"}, status=400)

    purchase_unit = result["purchase_units"][0]
    custom_id = purchase_unit.get("custom_id", "")
    amount = float(purchase_unit["payments"]["captures"][0]["amount"]["value"])
    payment_type, plan = custom_id.split("|") if "|" in custom_id else ("credit", "")

    wallet = Wallet.objects.get(user=request.user)

    if payment_type == "credit":
        wallet.balance += amount
        wallet.save()
        Transaction.objects.create(
            user=request.user,
            type="credit",
            amount=amount,
            description="Recharge via PayPal"
        )

    elif payment_type == "subscription" and plan:
        sub = Subscription.objects.get(user=request.user)
        sub.plan = plan
        sub.end_date = None if plan == "free" else timezone.now().date().replace(year=timezone.now().year + 1)
        sub.save()
        Transaction.objects.create(
            user=request.user,
            type="subscription",
            amount=amount,
            description=f"Abonnement {plan} via PayPal"
        )

    # ⚡ Attribution de la commission au parrain (points, pas wallet)
    if hasattr(request.user, 'referred_by'):
        ref = request.user.referred_by
        commission_points = amount * 0.05 * 1000  # 1000 points = 1€
        ReferralTransaction.objects.create(
            referral=ref,
            amount=commission_points,
            description=f"Commission sur {payment_type} de {request.user.username}",
            converted=False
        )

    # ✅ Mettre à jour le PaymentRequest correspondant
    try:
        payment = PaymentRequest.objects.get(user=request.user, amount=amount, status='pending', provider='paypal')
        payment.status = 'success'
        payment.save()
    except PaymentRequest.DoesNotExist:
        pass

    return JsonResponse({"success": True})


# ---------------- Dashboard ----------------
@login_required
def dashboard(request):
    wallet = Wallet.objects.get(user=request.user)
    subscription = Subscription.objects.get(user=request.user)
    usage, _ = UsageLog.objects.get_or_create(user=request.user, date=timezone.now().date())
    limits = get_plan_limits(request.user)

    return render(request, 'monetisation/dashboard.html', {
        'wallet': wallet,
        'subscription': subscription,
        'usage': usage,
        'limits': limits,
        'currency': settings.PAYPAL_CURRENCY  # ⚡ Ajout de la devise dynamique
    })


# ---------------- Acheter Crédit ----------------
@login_required
def buy_credit(request):
    wallet = Wallet.objects.get(user=request.user)

    if request.method == 'POST':
        amount = float(request.POST.get('amount', 0))
        provider = request.POST.get('provider', 'paypal')

        if amount <= 0:
            return JsonResponse({"error": "Montant invalide"}, status=400)

        payment = PaymentRequest.objects.create(
            user=request.user,
            provider=provider,
            amount=amount,
            status='pending',
            transaction_id=str(uuid.uuid4()),
        )

        # ⚡ Attribution commission au parrain (en points, pas wallet)
        if hasattr(request.user, 'referred_by'):
            ref = request.user.referred_by
            commission_points = amount * 0.05 * 1000  # 1000 pts = 1€
            ReferralTransaction.objects.create(
                referral=ref,
                amount=commission_points,
                description=f"Commission sur achat de {request.user.username}",
                converted=False
            )

        return redirect('monetisation:wallet_dashboard')

    return render(request, 'monetisation/acheter_credit.html', {'wallet': wallet})




# ---------------- Historique des Transactions ----------------
@login_required
def transactions(request):
    tx = Transaction.objects.filter(user=request.user).order_by('-timestamp')
    return render(request, 'monetisation/transactions.html', {"transactions": tx})


# ---------------- Gestion Abonnement ----------------
# Définition des prix des plans
PLAN_PRICES = {
    'free': 0,
    'basic': 0.1,
    'pro': 15
}

@login_required
def subscription_view(request):
    sub = Subscription.objects.get(user=request.user)
    wallet = Wallet.objects.get(user=request.user)

    if request.method == 'POST':
        new_plan = request.POST.get('plan')
        provider = request.POST.get('provider')
        amount = PLAN_PRICES.get(new_plan, 0)

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
            # Vérifier le solde
            if wallet.balance < amount:
                plans_info = [
                    {'name': k, **v, 'price': PLAN_PRICES[k]}
                    for k, v in PLAN_LIMITS.items()
                ]
                return render(request, 'monetisation/abonnement.html', {
                    'subscription': sub,
                    'plans': plans_info,
                    'wallet': wallet,
                    'error': f"Solde insuffisant dans le wallet ({wallet.balance} EUR)"
                })

            # Débiter le wallet
            wallet.balance -= amount
            wallet.save()

            # Mettre à jour l'abonnement
            sub.plan = new_plan
            sub.end_date = timezone.now().date().replace(year=timezone.now().year + 1)
            sub.save()

            # ⚡ Créer la transaction
            Transaction.objects.create(
                user=request.user,
                type='debit',
                amount=amount,
                description=f"Abonnement {new_plan} payé avec Wallet"
            )

            # ⚡ Créer le PaymentRequest avec status='success'
            PaymentRequest.objects.create(
                user=request.user,
                provider='wallet',
                amount=amount,
                status='success',
                transaction_id=str(uuid.uuid4())
            )

            # Attribution de la commission au parrain
            if hasattr(request.user, 'referred_by'):
                ref = request.user.referred_by
                commission = amount * 0.05
                wallet_referrer = Wallet.objects.get(user=ref.referrer)
                wallet_referrer.balance += commission
                wallet_referrer.save()
                ReferralTransaction.objects.create(
                    referral=ref,
                    amount=commission,
                    description=f"Commission sur abonnement de {request.user.username}"
                )

            return redirect('monetisation:payment_success')

        # --- Paiement via Mobile Money ou autre provider ---
        PaymentRequest.objects.create(
            user=request.user,
            provider=provider,
            amount=amount,
            status='pending',
            transaction_id=str(uuid.uuid4())
        )

        return redirect('monetisation:wallet_dashboard')

    # --- Préparer les informations des plans pour le template ---
    plans_info = []
    for plan_name, limits in PLAN_LIMITS.items():
        plans_info.append({
            'name': plan_name,
            'calls': limits['calls'],
            'devices': limits['devices'],
            'history_days': limits['history_days'],
            'alerts': limits['alerts'],
            'marketplace': limits['marketplace'],
            'pdf_reports': limits['pdf_reports'],
            'price': PLAN_PRICES[plan_name],
        })

    return render(request, 'monetisation/abonnement.html', {
        'subscription': sub,
        'plans': plans_info,
        'wallet': wallet
    })
# ---------------- Dashboard Wallet ----------------
@login_required
def wallet_dashboard(request):
    wallet = Wallet.objects.get(user=request.user)
    payments = PaymentRequest.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'monetisation/wallet_dashboard.html', {
        'wallet': wallet,
        'payments': payments
    })


# ---------------- Initier Paiement Mobile Money ----------------
@login_required
def init_mobile_money(request):
    wallet = Wallet.objects.get(user=request.user)

    if request.method == 'POST':
        provider = request.POST.get('provider')
        phone_number = request.POST.get('phone_number', '')
        amount = float(request.POST.get('amount', 0))

        # Vérification basique
        if amount <= 0:
            return render(request, 'monetisation/init_mobile_money.html', {
                'wallet': wallet,
                'error': "Veuillez saisir un montant valide."
            })

        # Créer un PaymentRequest
        payment = PaymentRequest.objects.create(
            user=request.user,
            provider=provider,
            phone_number=phone_number,
            amount=amount,
            transaction_id=str(uuid.uuid4()),
            status='pending'
        )

        # Pour PayPal, rediriger vers le dashboard et laisser le front gérer l'ordre
        if provider.lower() == 'paypal':
            return redirect('monetisation:wallet_dashboard')

        # Pour Mobile Money, normalement tu enverras une requête à l'API du fournisseur
        # Ici on reste en simulation pour test
        # Exemple :
        # send_mobile_money_request(provider, phone_number, amount, payment.transaction_id)

        return redirect('monetisation:wallet_dashboard')

    return render(request, 'monetisation/init_mobile_money.html', {
        'wallet': wallet,
        'currency': 'EUR'  # ou 'EUR', selon ton paramètre PayPal
    })


# ---------------- Callback Mobile Money ----------------
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse

@csrf_exempt
def mobile_money_callback(request):
    """
    Callback Mobile Money. Créditer le wallet utilisateur et le parrain après paiement réussi.
    """
    data = json.loads(request.body)
    try:
        pr = PaymentRequest.objects.get(transaction_id=data['transaction_id'])
        wallet = Wallet.objects.get(user=pr.user)

        if data['status'] == 'SUCCESS':
            pr.status = 'success'
            wallet.balance += pr.amount
            wallet.save()

            Transaction.objects.create(
                user=pr.user,
                type='credit',
                amount=pr.amount,
                description=f"Recharge via {pr.provider}"
            )

            # ⚡ Attribution commission au parrain
            if hasattr(pr.user, 'referred_by'):
                ref = pr.user.referred_by
                commission = pr.amount * 0.05
                wallet_referrer = Wallet.objects.get(user=ref.referrer)
                wallet_referrer.balance += commission
                wallet_referrer.save()
                ReferralTransaction.objects.create(
                    referral=ref,
                    amount=commission,
                    description=f"Commission sur recharge de {pr.user.username}"
                )

        else:
            pr.status = 'failed'

        pr.save()
        return JsonResponse({"message": "OK"})

    except PaymentRequest.DoesNotExist:
        return JsonResponse({"message": "Payment not found"}, status=404)


from monetisation.quota import get_limits_for_user
from monetisation.models import UsageLog
from django.utils import timezone

def dashboard(request):
    wallet = Wallet.objects.get(user=request.user)
    subscription = Subscription.objects.get(user=request.user)
    limits, plan = get_limits_for_user(request.user)
    usage = UsageLog.objects.filter(user=request.user, date=timezone.now().date()).first()
    usage = usage or type("u", (), {"api_calls": 0, "device_count": 0})()
    return render(request, 'monetisation/dashboard.html', {
        'wallet': wallet,
        'subscription': subscription,
        'limits': limits,
        'usage': usage,
        'plan': plan
    })





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
    total_commissions = sum(c.amount for c in commissions if not c.converted)

    # Conversion ratio (ex: 1000 points = 1€)
    POINTS_PER_EURO = 0.001  # ⚡ défini ici pour template et calcul

    return render(request, 'monetisation/referrals.html', {
        'referral_code': referral_code,
        'referrals': referrals,
        'commissions': commissions,           # Affichage complet
        'total_commissions': total_commissions,  # Total non converti
        'POINTS_PER_EURO': POINTS_PER_EURO    # Envoi au template
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


POINTS_PER_EURO = 1000      # 1000 points = 1€
MIN_POINTS_REQUIRED = 0.001 # minimum pour convertir

@login_required
def convert_commission_to_wallet(request):
    user = request.user

    commissions = ReferralTransaction.objects.filter(
        referral__referrer=user,
        converted=False
    )

    total_points = sum(c.amount for c in commissions)

    if total_points < MIN_POINTS_REQUIRED:
        messages.error(request, "Vous n'avez pas assez de points pour convertir.")
        return redirect('monetisation:referral_dashboard')

    wallet_credit = total_points / POINTS_PER_EURO

    wallet, _ = Wallet.objects.get_or_create(user=user)
    wallet.balance += wallet_credit
    wallet.save()

    commissions.update(amount=0, converted=True)

    messages.success(
        request,
        f"Vous avez converti {total_points} points en {wallet_credit:.4f} € dans votre Wallet !"
    )

    return redirect('monetisation:wallet_dashboard')

@login_required
def payment_success(request):
    return render(request, "monetisation/payment_success.html")

