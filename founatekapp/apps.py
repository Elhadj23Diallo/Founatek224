from django.apps import AppConfig


class FounatekappConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'founatekapp'
    verbose_name = 'FOUNATEK SHOP'

    def ready(self):
        import founatekapp.signals  # noqa

