from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.conf import settings

from .models import Wallet, Subscription, PaymentRequest

@receiver(post_save, sender=User)
def create_wallet(sender, instance, created, **kwargs):
    if created:
        Wallet.objects.create(user=instance)
        Subscription.objects.create(user=instance)


ADMIN_NOTIFICATION_EMAILS = ['jallohelhadjabdul@gmail.com', 'dialloelhadjabdourahmane510@gmail.com']


@receiver(post_save, sender=PaymentRequest)
def notify_admin_new_payment_request(sender, instance, created, **kwargs):
    """Notifie les admins par email des qu'une demande de paiement Mobile Money arrive,
    pour confirmation manuelle (pas d'API automatisee sans entreprise enregistree)."""
    if not created:
        return
    try:
        subject = f"FOUNATEK — Nouvelle demande {instance.provider} de {instance.amount} EUR"
        body = (
            f"Nouvelle demande de paiement Mobile Money a confirmer.\n\n"
            f"Utilisateur : {instance.user.username} ({instance.user.email})\n"
            f"Opérateur   : {instance.provider}\n"
            f"Téléphone   : {instance.phone_number}\n"
            f"Montant     : {instance.amount} EUR\n"
            f"Référence   : {instance.transaction_id or 'Non fournie'}\n\n"
            f"Confirmez ou refusez cette demande depuis l'app (onglet Admin Paiements) "
            f"ou l'admin Django."
        )
        send_mail(
            subject=subject, message=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=ADMIN_NOTIFICATION_EMAILS,
            fail_silently=True,
        )
    except Exception:
        pass
