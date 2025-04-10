from django.db import models

class LED(models.Model):
    etat = models.BooleanField(default=False)

    def __str__(self):
        return "LED allumée" if self.etat else "LED éteinte"


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



class Comptage(models.Model):
    compteur = models.IntegerField(default=0)  # Nombre d'objets comptés
    timestamp = models.DateTimeField(auto_now_add=True)  # Date et heure de l'enregistrement

    def __str__(self):
        return f"Comptage: {self.compteur} objets - {self.timestamp}"
