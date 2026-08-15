from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from .models import Order, LoyaltyAccount


@receiver(post_save, sender=User)
def create_loyalty_account(sender, instance, created, **kwargs):
    """Crée automatiquement un compte fidélité Ã  l'inscription."""
    if created:
        LoyaltyAccount.objects.get_or_create(user=instance)


def send_admin_order_notification(order):
    """Notifie le vendeur/admin par email de la nouvelle commande."""
    from django.conf import settings as dj_settings
    recipients = ['jallohelhadjabdul@gmail.com', 'dialloelhadjabdourahmane510@gmail.com']
    if not recipients:
        return
    subject = f'Nouvelle commande #{order.pk:06d} - FOUNATEK SHOP'
    client_name = order.user.get_full_name() or order.user.username
    body = (
        f"Nouvelle commande recue sur FOUNATEK SHOP.\n\n"
        f"Numero de commande : #{order.pk:06d}\n"
        f"Client : {client_name}\n"
        f"Telephone : {order.phone}\n"
        f"Email : {order.contact_email or order.user.email}\n"
        f"Adresse de livraison : {order.shipping_address}\n"
        f"Mode de paiement : {order.get_payment_method_display() if hasattr(order, 'get_payment_method_display') else order.payment_method}\n"
        f"Total : {order.total} GNF\n\n"
        f"Connectez-vous a l'admin pour voir le detail complet et confirmer le paiement."
    )
    try:
        send_mail(
            subject=subject,
            message=body,
            from_email=dj_settings.DEFAULT_FROM_EMAIL,
            recipient_list=recipients,
            fail_silently=True,
        )
    except Exception:
        pass


def send_order_email(order, earned, loyalty):
    """Envoie l'email de confirmation de commande."""
    recipient = order.contact_email or order.user.email
    if not recipient:
        return
    subject = f'FOUNATEK SHOP — Confirmation commande #{order.pk:06d}'
    try:
        body = render_to_string('store/emails/order_confirmation.txt', {
            'order': order,
            'earned': earned,
            'loyalty': loyalty,
        })
        send_mail(
            subject=subject,
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient],
            fail_silently=True,
        )
    except Exception:
        pass

