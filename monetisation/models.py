from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import uuid
from django.db import models
from django.contrib.auth.models import User

# Montants en euros : DecimalField à 2 décimales (plus de 9900.709999999997).
# Toujours passer par utils.round_money() pour les calculs.
MONEY = dict(max_digits=12, decimal_places=2)


class Wallet(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    # Peut devenir négatif si un paiement déjà dépensé est remboursé ou contesté.
    balance = models.DecimalField(default=0, **MONEY)

    def __str__(self):
        return f"Wallet de {self.user.username} : {self.balance} crédits"


class Transaction(models.Model):
    TYPE_CHOICES = [
        ('credit', 'Ajout de crédits'),
        ('debit', 'Débit de crédits'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    type = models.CharField(max_length=10, choices=TYPE_CHOICES)
    amount = models.DecimalField(**MONEY)
    timestamp = models.DateTimeField(default=timezone.now)
    description = models.CharField(max_length=255)

    def __str__(self):
        return f"{self.user.username} - {self.type} - {self.amount}"


class Subscription(models.Model):
    PLAN_CHOICES = [
        ('free', 'Gratuit'),
        ('basic', 'Basic'),
        ('pro', 'Pro'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    plan = models.CharField(max_length=20, choices=PLAN_CHOICES, default='free')
    start_date = models.DateField(default=timezone.now)
    end_date = models.DateField(null=True, blank=True)
    # Résiliation différée : l'utilisateur garde le plan payant jusqu'à end_date,
    # mais ne sera plus jamais relancé pour renouveler (pas de reconduction
    # automatique dans ce systeme, donc ce champ est purement informatif/UX —
    # voir monetisation.utils.sync_subscription_expiry pour le retour au gratuit).
    cancel_at_period_end = models.BooleanField(default=False)

    # Paiement : « manual » = 30 jours payés une fois (wallet ou PayPal), sans
    # renouvellement ; « stripe_auto » = carte enregistrée chez Stripe et
    # prélèvement automatique chaque mois (voir monetisation/saas_billing.py).
    BILLING_CHOICES = [
        ("manual", "Paiement ponctuel (30 jours)"),
        ("stripe_auto", "Carte, renouvellement automatique"),
    ]
    billing = models.CharField(max_length=20, choices=BILLING_CHOICES, default="manual")
    stripe_customer_id = models.CharField(max_length=255, blank=True, default="")
    stripe_subscription_id = models.CharField(max_length=255, blank=True, default="", db_index=True)
    last_stripe_invoice_id = models.CharField(max_length=255, blank=True, default="")
    # Accord exprès : CGV, renouvellement automatique, début immédiat du service
    auto_renew_consent_at = models.DateTimeField(null=True, blank=True)

    @property
    def auto_renew_active(self):
        return self.billing == "stripe_auto" and bool(self.stripe_subscription_id) and not self.cancel_at_period_end

    def __str__(self):
        return f"{self.user.username} - {self.plan}"


class PaymentRequest(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    provider = models.CharField(max_length=50)  # MTN, Orange, Moov, Wave
    phone_number = models.CharField(max_length=20)
    amount = models.DecimalField(**MONEY)  # Montant credite au wallet, en EUR (devise interne du wallet)
    amount_local = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True)  # Montant reellement envoye par l'utilisateur (ex: en GNF)
    currency_local = models.CharField(max_length=3, default='GNF')  # Devise du montant envoye
    # pending, success, failed, refunded (remboursé en totalité), disputed (litige en cours)
    status = models.CharField(max_length=20, default='pending')
    transaction_id = models.CharField(max_length=100, null=True, blank=True)
    # Identifiant du paiement chez le prestataire, pour retrouver la demande
    # lors d'un remboursement ou d'un litige : PaymentIntent Stripe (pi_...)
    # ou capture PayPal.
    external_id = models.CharField(max_length=255, blank=True, default='', db_index=True)
    # 'credit' (recharge du wallet) ou 'subscription' (abonnement PayPal direct)
    purpose = models.CharField(max_length=20, blank=True, default='credit')
    refunded_amount = models.DecimalField(default=0, **MONEY)
    # Montant bloqué pendant un litige (rendu si le litige est gagné)
    disputed_amount = models.DecimalField(default=0, **MONEY)
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='payment_requests_reviewed')
    reviewed_at = models.DateTimeField(null=True, blank=True)


class MobileMoneyAccount(models.Model):
    """Numeros Mobile Money du marchand (Founatek) affiches aux clients pour paiement manuel,
    en attendant une integration API complete (necessite une entreprise enregistree/RCCM)."""
    provider = models.CharField(max_length=50)  # MTN, Orange, Moov, Wave
    phone_number = models.CharField(max_length=20)
    owner_name = models.CharField(max_length=100, help_text="Nom du titulaire du compte, affiche au client")
    is_active = models.BooleanField(default=True)
    instructions = models.CharField(max_length=255, blank=True, help_text="Instructions optionnelles affichees au client")

    class Meta:
        ordering = ['provider']

    def __str__(self):
        return f"{self.provider} — {self.phone_number}"


# monetisation/models.py (ou espcontrol/models.py selon ton projet)
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

class UsageLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    date = models.DateField(default=timezone.now)
    api_calls = models.IntegerField(default=0)
    device_count = models.IntegerField(default=0)
    # Appels aux API IoT (ingestion ESP32, relais, LED, accès...) authentifiés
    # par token — distinct de api_calls, qui n'est jamais incrémenté en pratique.
    iot_calls = models.IntegerField(default=0)

    class Meta:
        unique_together = ('user', 'date')

    def __str__(self):
        return f"{self.user.username} - {self.date} - calls:{self.api_calls} devices:{self.device_count}"


#Parrainage
# ---------------- Parrainage ----------------
class Referral(models.Model):
    referrer = models.ForeignKey(
        User, related_name='referrals_made',
        on_delete=models.CASCADE, null=True, blank=True
    )  # Le parrain, peut être null si pas de code utilisé
    referred = models.OneToOneField(
        User, related_name='referred_by',
        on_delete=models.CASCADE
    )  # Le nouvel utilisateur
    code = models.CharField(max_length=36, unique=True, default=uuid.uuid4)  # code unique
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.referred.username} <- {self.referrer.username if self.referrer else 'None'}"

    def clean(self):
        # Bloque l'auto-parrainage dans l'admin (le paiement l'ignore aussi :
        # voir utils.award_referral_commission).
        from django.core.exceptions import ValidationError
        if self.referrer_id and self.referrer_id == self.referred_id:
            raise ValidationError("Un utilisateur ne peut pas être son propre parrain.")

# ---------------- Commissions ----------------
class ReferralTransaction(models.Model):
    referral = models.ForeignKey(Referral, on_delete=models.CASCADE)
    amount = models.DecimalField(**MONEY)  # Commission, en points (1 000 points = 1 €)
    # Paiement qui a donné cette commission : si le filleul est remboursé,
    # la commission non convertie est annulée.
    payment = models.ForeignKey('PaymentRequest', null=True, blank=True, on_delete=models.SET_NULL, related_name='commissions')
    description = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    converted = models.BooleanField(default=False)  # ← Nouveau champ

    def __str__(self):
        referrer = self.referral.referrer.username if self.referral.referrer else "(sans parrain)"
        return f"{referrer} gagne {self.amount:g} points de {self.referral.referred.username}"
