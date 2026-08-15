from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from django.utils.timezone import localtime

from .models import AppareilData, Device, AgentAlert


@receiver(post_save, sender=AppareilData)
def update_device_last_seen(sender, instance, created, **kwargs):
    """Met à jour `Device.last_seen` lorsque de nouvelles données arrivent."""
    try:
        device = instance.device
        device.last_seen = instance.received_at or timezone.now()
        device.save(update_fields=["last_seen"])
    except Exception:
        # Ne pas faire échouer la chaîne d'enregistrement
        pass


@receiver(post_save, sender=AgentAlert)
def send_alert_email(sender, instance, created, **kwargs):
    """Envoie un email a l'utilisateur des qu'une nouvelle alerte est creee."""
    if not created:
        return
    try:
        recipient = instance.user.email
        if not recipient:
            return
        level_labels = {"INFO": "Information", "WARN": "⚠️ Avertissement", "CRITICAL": "🔴 Critique"}
        level_label = level_labels.get(instance.level, instance.level)
        device_name = instance.device.name if instance.device else "Appareil inconnu"
        ts = localtime(instance.created_at).strftime("%d/%m/%Y %H:%M")
        subject = f"FOUNATEK — Nouvelle alerte [{instance.level}] {device_name}"
        body = (
            f"Bonjour {instance.user.username},\n\n"
            f"Une nouvelle alerte a ete detectee sur votre compte FOUNATEK.\n\n"
            f"Niveau     : {level_label}\n"
            f"Appareil   : {device_name}\n"
            f"Capteur    : {instance.sensor or 'N/A'}\n"
            f"Valeur     : {instance.value if instance.value is not None else 'N/A'}\n"
            f"Message    : {instance.message}\n"
            f"Date       : {ts}\n\n"
            f"Consultez le module Alertes dans l'application ou le tableau de bord pour plus de details.\n\n"
            f"— FOUNATEK NEXUS"
        )
        send_mail(
            subject=subject,
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient],
            fail_silently=True,
        )
    except Exception:
        # Ne jamais faire echouer la creation de l'alerte a cause de l'email
        pass
