from django.db.models.signals import m2m_changed, post_save
from django.dispatch import receiver
from django.contrib.auth.models import Group
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.conf import settings

from .models import FormateurProfile, Organisation, Certification, Parcours, FormateurFollow
from django.db.models.signals import pre_save

@receiver(m2m_changed, sender=User.groups.through)
def create_formateur_profile(sender, instance, action, pk_set, **kwargs):
    if action == "post_add":
        try:
            formateur_group = Group.objects.get(name="Formateur")
        except Group.DoesNotExist:
            return

        if formateur_group.pk in pk_set:
            FormateurProfile.objects.get_or_create(
                user=instance,
                defaults={
                    # ⚠️ organisation à définir manuellement ensuite via admin
                    "organisation": Organisation.objects.first()
                }
            )


@receiver(pre_save, sender=Organisation)
def regenerate_certificates_on_logo_change(sender, instance, **kwargs):
    if not instance.pk:
        return

    old = Organisation.objects.get(pk=instance.pk)

    if old.logo != instance.logo:
        certifications = Certification.objects.filter(
            parcours__organisation=instance
        )

        for cert in certifications:
            # 🔥 SUPPRESSION DU PDF EXISTANT
            if cert.pdf:
                cert.pdf.delete(save=False)

            cert.pdf = None
            cert.pdf_generated_at = None
            cert.save(update_fields=["pdf", "pdf_generated_at"])


@receiver(pre_save, sender=Parcours)
def _memorize_previous_publish_state(sender, instance, **kwargs):
    """Retient l'etat is_published avant sauvegarde, pour detecter une publication."""
    if not instance.pk:
        instance._was_published = False
        return
    try:
        instance._was_published = Parcours.objects.get(pk=instance.pk).is_published
    except Parcours.DoesNotExist:
        instance._was_published = False


@receiver(post_save, sender=Parcours)
def notify_followers_on_publish(sender, instance, created, **kwargs):
    """Previent par email les abonnes du formateur quand un parcours passe en publie."""
    was_published = getattr(instance, "_was_published", False)
    if was_published or not instance.is_published:
        return

    followers = FormateurFollow.objects.filter(
        formateur=instance.created_by
    ).select_related("follower")

    for follow in followers:
        recipient = follow.follower.email
        if not recipient:
            continue
        try:
            send_mail(
                subject=f"FOUNATEK — {instance.created_by.username} vient de publier un nouveau cours",
                message=(
                    f"Bonjour {follow.follower.username},\n\n"
                    f"Le formateur que vous suivez, {instance.created_by.username}, vient de publier "
                    f"un nouveau parcours :\n\n"
                    f"« {instance.titre} »\n"
                    f"Niveau : {instance.niveau}\n\n"
                    f"Rendez-vous sur Founatek pour le découvrir.\n\n"
                    f"— FOUNATEK NEXUS"
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[recipient],
                fail_silently=True,
            )
        except Exception:
            pass