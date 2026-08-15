from django.apps import AppConfig

class OscilloscopeConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'oscilloscope_app'   # ✅ doit matcher le nom du dossier
    verbose_name = 'Oscilloscope Numérique — Founatek'