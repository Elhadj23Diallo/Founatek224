from django.db.models.signals import post_save
from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone, translation
from django.utils.timezone import localtime

from .models import AppareilData, Device, AgentAlert, ProactiveChatMessage


@receiver(user_logged_in)
def activate_user_language(sender, request, user, **kwargs):
    """Applique immediatement la langue enregistree dans le profil des la
    reponse de connexion elle-meme — les requetes suivantes sont prises en
    charge par UserLanguageMiddleware (middleware/user_language_middleware.py),
    qui relit le profil a chaque fois."""
    try:
        from .models import UserProfile
        lang = UserProfile.objects.get(user=user).language
    except Exception:
        lang = settings.LANGUAGE_CODE
    translation.activate(lang)


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


@receiver(post_save, sender=AgentAlert)
def create_proactive_chat_message(sender, instance, created, **kwargs):
    """Le chatbot 'parle en premier' des qu'une alerte est detectee — le
    message attend d'etre recupere par le widget de chat (site/mobile) au
    prochain sondage, voir chatbot_proactive_pending / mobile_chatbot_proactive."""
    if not created:
        return
    try:
        level_icons = {"INFO": "ℹ️", "WARN": "⚠️", "CRITICAL": "🔴"}
        icon = level_icons.get(instance.level, "🔔")
        device_name = instance.device.name if instance.device else "un appareil"
        text = (
            f"{icon} Je viens de détecter une alerte [{instance.level}] sur {device_name} : "
            f"{instance.message}. Dites-moi si vous voulez que je vous en dise plus ou que j'agisse."
        )
        ProactiveChatMessage.objects.create(user=instance.user, alert=instance, text=text)
    except Exception:
        pass
