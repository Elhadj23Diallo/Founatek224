from django.apps import AppConfig


class ProductTransparencyConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "product_transparency"

    def ready(self):
        import product_transparency.signals
