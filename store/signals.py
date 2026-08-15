from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from .models import Order, LoyaltyAccount


@receiver(post_save, sender=User)
def create_loyalty_account(sender, instance, created, **kwargs):
    """Crée automatiquement un compte fidélité à l'inscription."""
    if created:
        LoyaltyAccount.objects.get_or_create(user=instance)


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
