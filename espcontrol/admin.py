from django.contrib import admin
from .models import DHTData, UploadedImage, LED, Comptage
@admin.register(UploadedImage)
class UploadedImageAdmin(admin.ModelAdmin):
    list_display = ('id', 'created_at', 'image')
    search_fields = ('id',)

class DHTDataAdmin(admin.ModelAdmin):
    list_display = ('temperature', 'humidity', 'created_at')  # Afficher les colonnes dans l'admin
    list_filter = ('created_at',)  # Filtrer par date
    search_fields = ('temperature', 'humidity')  # Permet de rechercher par température et humidité

# Enregistrer le modèle dans l'admin
admin.site.register(DHTData, DHTDataAdmin)


admin.site.register(LED)
admin.site.register(Comptage)

