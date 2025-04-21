from django.db import models

class LED(models.Model):
    etat = models.BooleanField(default=False)

    def __str__(self):
        return "LED allumée" if self.etat else "LED éteinte"


#capteur de température et d'humidité du sol
class SoilData(models.Model):
    humidity = models.IntegerField()  # Humidité du sol
    created_at = models.DateTimeField(auto_now_add=True)  # Date de création, automatique

    def __str__(self):
        return f"Humidité: {self.humidity} à {self.created_at}"

class DHTData(models.Model):
    temperature = models.FloatField()  # Température mesurée par le capteur DHT11
    humidity = models.FloatField()  # Humidité mesurée par le capteur DHT11
    created_at = models.DateTimeField(auto_now_add=True)  # Date et heure de la lecture

    def __str__(self):
        return f"Temp: {self.temperature}°C, Humidity: {self.humidity}%"


# surveillance/models.py
from django.db import models

class UploadedImage(models.Model):
    image = models.ImageField(upload_to='images/')  # Le champ pour stocker l'image
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Image {self.id} - {self.created_at}"

from django.db import models

class Video(models.Model):
    video = models.FileField(upload_to='videos/')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Video {self.id} - {self.created_at}"


# views.py
import base64
import io
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.core.files.base import ContentFile
from PIL import Image
from io import BytesIO

@csrf_exempt  # Ignore le CSRF pour faciliter les tests
def upload_image(request):
    if request.method == 'POST':
        data = request.body.decode('utf-8')  # Récupère les données JSON
        try:
            # Extraire l'image base64
            start = data.find('image":"') + 8
            end = data.find('"', start)
            image_data = data[start:end]

            # Convertir l'image de base64 en image binaire
            img_data = base64.b64decode(image_data)
            image = Image.open(io.BytesIO(img_data))

            # Sauvegarder l'image dans un fichier ou base de données
            image_name = 'uploaded_image.jpg'
            image_path = '/path/to/save/images/' + image_name
            image.save(image_path)

            return JsonResponse({"status": "success", "message": "Image uploadée avec succès!"})

        except Exception as e:
            return JsonResponse({"status": "error", "message": str(e)})

    return JsonResponse({"status": "error", "message": "Méthode non supportée"})



class Comptage(models.Model):
    compteur = models.IntegerField(default=0)  # Nombre d'objets comptés
    timestamp = models.DateTimeField(auto_now_add=True)  # Date et heure de l'enregistrement

    def __str__(self):
        return f"Comptage: {self.compteur} objets - {self.timestamp}"

#models pour le capteur de gaz
from django.db import models

class GasData(models.Model):
    timestamp = models.DateTimeField(auto_now_add=True)
    ppm = models.FloatField()
    gaz_type = models.CharField(max_length=20, default='inconnu')  # ex: CO2, NH3, Benzène

    def __str__(self):
        return f"{self.gaz_type} : {self.ppm} ppm @ {self.timestamp}"
