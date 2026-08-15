from django.db.models.signals import m2m_changed
from django.dispatch import receiver
from django.contrib.auth.models import Group
from django.contrib.auth.models import User

from .models import FormateurProfile, Organisation, Certification
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