from django.apps import AppConfig


class EspcontrolConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'espcontrol'

    def ready(self):
        # Importer les signaux pour qu'ils soient enregistrés
        try:
            import espcontrol.signals  # noqa: F401
        except Exception:
            pass
