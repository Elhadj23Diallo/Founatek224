from django.db import models
from django.contrib.auth.models import User  # Importer le modèle User

class LED(models.Model):
    etat = models.BooleanField(default=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
  # Lier chaque LED à un utilisateur

    def __str__(self):
        return "LED allumée" if self.etat else "LED éteinte"

# Capteur de température et d'humidité du sol
class SoilData(models.Model):
    humidity = models.IntegerField()  # Humidité du sol
    created_at = models.DateTimeField(auto_now_add=True)  # Date de création, automatique
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
  # Lier les données à un utilisateur

    def __str__(self):
        return f"Humidité: {self.humidity} à {self.created_at}"

# Modèle pour le relais
class Relais(models.Model):
    num = models.IntegerField(unique=True)  # Le numéro du relais
    etat = models.BooleanField(default=False)  # L'état du relais (True = allumé, False = éteint)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
  # Lier le relais à un utilisateur

    def __str__(self):
        return f"Relais {self.num} {'allumé' if self.etat else 'éteint'}"

# Données du capteur DHT11
class DHTData(models.Model):
    temperature = models.FloatField()  # Température mesurée par le capteur DHT11
    humidity = models.FloatField()  # Humidité mesurée par le capteur DHT11
    created_at = models.DateTimeField(auto_now_add=True)  # Date et heure de la lecture
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
  # Lier les données à un utilisateur

    def __str__(self):
        return f"Temp: {self.temperature}°C, Humidity: {self.humidity}%"

# Modèle pour les images téléchargées
class UploadedImage(models.Model):
    image = models.ImageField(upload_to='images/')  # Le champ pour stocker l'image
    created_at = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
  # Lier l'image à un utilisateur

    def __str__(self):
        return f"Image {self.id} - {self.created_at}"

# Modèle pour les vidéos
class Video(models.Model):
    video = models.FileField(upload_to='videos/')
    created_at = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
  # Lier la vidéo à un utilisateur

    def __str__(self):
        return f"Video {self.id} - {self.created_at}"

# Comptage des objets
class Comptage(models.Model):
    compteur = models.IntegerField(default=0)  # Nombre d'objets comptés
    timestamp = models.DateTimeField(auto_now_add=True)  # Date et heure de l'enregistrement
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
  # Lier le comptage à un utilisateur

    def __str__(self):
        return f"Comptage: {self.compteur} objets - {self.timestamp}"

# Modèle pour le capteur de gaz
class GasData(models.Model):
    timestamp = models.DateTimeField(auto_now_add=True)
    ppm = models.FloatField()
    gaz_type = models.CharField(max_length=20, default='inconnu')  # ex: CO2, NH3, Benzène
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
  # Lier les données à un utilisateur

    def __str__(self):
        return f"{self.gaz_type} : {self.ppm} ppm @ {self.timestamp}"
