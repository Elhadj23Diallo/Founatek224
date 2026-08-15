from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from espcontrol.models import UploadedImage # Assure-toi que le nom de l'app est bon
import os

class Command(BaseCommand):
    help = 'Supprime les images vieilles de plus de X heures pour libérer de la place'

    def handle(self, *args, **kwargs):
        # ⏱️ Config : On garde seulement les 24 dernières heures
        time_threshold = timezone.now() - timedelta(hours=24)
        
        # Sélectionner les vieilles images
        old_images = UploadedImage.objects.filter(created_at__lt=time_threshold)
        count = old_images.count()

        if count == 0:
            self.stdout.write("✅ Aucune vieille image à supprimer.")
            return

        self.stdout.write(f"🗑️ Suppression de {count} images...")

        for img in old_images:
            # 1. Supprimer le fichier physique du disque
            try:
                if img.image and os.path.isfile(img.image.path):
                    os.remove(img.image.path)
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Erreur suppression fichier {img.id}: {e}"))
            
            # 2. Supprimer l'entrée en base de données
            img.delete()

        self.stdout.write(self.style.SUCCESS(f"✅ Terminé ! {count} images supprimées."))