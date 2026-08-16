from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import uuid
from django.db import models
from django.contrib.auth.models import User

class Wallet(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    balance = models.FloatField(default=0)

    def __str__(self):
        return f"Wallet de {self.user.username} : {self.balance} crédits"


class Transaction(models.Model):
    TYPE_CHOICES = [
        ('credit', 'Ajout de crédits'),
        ('debit', 'Débit de crédits'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    type = models.CharField(max_length=10, choices=TYPE_CHOICES)
    amount = models.FloatField()
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

    def __str__(self):
        return f"{self.user.username} - {self.plan}"


class PaymentRequest(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    provider = models.CharField(max_length=50)  # MTN, Orange, Moov, Wave
    phone_number = models.CharField(max_length=20)
    amount = models.FloatField()
    status = models.CharField(max_length=20, default='pending')  # pending, success, failed
    transaction_id = models.CharField(max_length=100, null=True, blank=True)
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
    # autres compteurs possibles : storage_mb = models.IntegerField(default=0)

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

# ---------------- Commissions ----------------
class ReferralTransaction(models.Model):
    referral = models.ForeignKey(Referral, on_delete=models.CASCADE)
    amount = models.FloatField()  # Crédit ou commission
    description = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    converted = models.BooleanField(default=False)  # ← Nouveau champ

    def __str__(self):
        return f"{self.referral.referrer.username} gains {self.amount} GNF from {self.referral.referred.username}"
