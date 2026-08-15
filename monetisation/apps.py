from django.apps import AppConfig


class MonetisationConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "monetisation"

    def ready(self):
        import monetisation.signals
