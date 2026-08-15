# product_transparency/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Product
from .services.qr_service import generate_qr_for_product

@receiver(post_save, sender=Product)
def create_product_qr(sender, instance, created, **kwargs):
    if created:
        generate_qr_for_product(instance)
