from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from .models import AppareilData, Device


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
