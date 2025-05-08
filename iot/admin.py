from django.contrib import admin
from .models import Chapitre, Projects

# Enregistrer le modèle dans l'admin
admin.site.register(Chapitre)
admin.site.register(Projects)