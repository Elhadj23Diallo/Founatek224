from django.apps import AppConfig


class AcountConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'acount'

    def ready(self):
        import acount.signals  # ← Assure-toi que le nom du module est correct

    
