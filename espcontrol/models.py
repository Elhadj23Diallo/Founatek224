from django.db import models
from django.contrib.auth.models import User  # Importer le modèle User
from django.conf import settings



# espcontrol/models.py

#Api generique universel

class Device(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="devices"
    )
    device_id = models.CharField(max_length=100, unique=True)
    name = models.CharField(max_length=100)
    api_key = models.CharField(max_length=255, unique=True)
    is_active = models.BooleanField(default=True)
    # Dernière fois où le device a envoyé des données
    last_seen = models.DateTimeField(null=True, blank=True, db_index=True)




class AppareilData(models.Model):
    device = models.ForeignKey(Device, on_delete=models.CASCADE)
    payload = models.JSONField()  # 👈 DONNÉES DYNAMIQUES
    received_at = models.DateTimeField(auto_now_add=True)
    is_anomaly = models.BooleanField(default=False)  # ← flag détection anomalies

    class Meta:
        ordering = ["-received_at"]


class AirReading(models.Model):
    # état
    is_active = models.BooleanField(default=True)

    # temps
    simulated_time = models.DateTimeField(db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    # localisation
    latitude = models.FloatField()
    longitude = models.FloatField()

    # polluants
    pm2p5 = models.FloatField()
    pm10 = models.FloatField()
    co = models.FloatField()
    no2 = models.FloatField()

    # origine & fiabilité 🔑
    origin = models.CharField(
        max_length=16,
        choices=[
            ("real", "Capteur réel"),
            ("virtual", "Capteur virtuel"),
            ("hybrid", "Hybride"),
        ],
        default="virtual",
        db_index=True,
    )

    confidence = models.FloatField(
        default=0.6,  # capteur virtuel par défaut
        help_text="Niveau de fiabilité entre 0 et 1",
    )

    source = models.CharField(max_length=64)

    class Meta:
        ordering = ["-simulated_time"]




class AirSimulatedData(models.Model):
    simulated_time = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    latitude = models.FloatField()
    longitude = models.FloatField()

    pm2p5 = models.FloatField()
    pm10 = models.FloatField()
    co = models.FloatField()
    no2 = models.FloatField()

    source = models.CharField(max_length=50, default="CAMS_SIM")

    class Meta:
        ordering = ["-simulated_time"]




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
    num = models.IntegerField()
    etat = models.BooleanField(default=False)
    # AJOUT : Nom pour la commande vocale (ex: "Lumière Salon", "Ventilateur")
    nom = models.CharField(max_length=100, default="Appareil Inconnu")
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)

    class Meta:
        unique_together = ('user', 'num')

    def __str__(self):
        return f"{self.nom} (Relais {self.num}) : {'ON' if self.etat else 'OFF'}"

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
    image = models.ImageField(upload_to='images/')
    created_at = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    # 🔥 multi-cam : identifiant envoyé par l’ESP32 (ex: "camera_salon")
    camera_id = models.CharField(max_length=100, null=True, blank=True)

    # 🧠 IA simple : flags analysés côté serveur
    has_motion = models.BooleanField(default=False)   # mouvement détecté ?
    has_person = models.BooleanField(default=False)   # TODO : pour après (vraie IA)
    has_vehicle = models.BooleanField(default=False)  # TODO : pour après

    def __str__(self):
        username = self.user.username if self.user else "Utilisateur supprimé"
        return f"Image {self.id} - {username} - {self.camera_id or 'no_cam'} - {self.created_at}"





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


#Systeme de controle de l'atmosphère

from django.contrib.auth.models import User

class SensorData(models.Model):
    temperature = models.FloatField()
    humidity = models.FloatField()
    co2 = models.IntegerField()
    timestamp = models.DateTimeField()
    gaz_type = models.CharField(max_length=20, default='inconnu')  # Le type de gaz détecté
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)

    def __str__(self):
        return f"{self.timestamp} | Temp={self.temperature}°C, Hum={self.humidity}%, CO2={self.co2}ppm, Gaz={self.gaz_type}"

#modele pour la thermistance
class NtcSensorData(models.Model):
    temperature = models.FloatField()  # Température mesurée par la thermistance
    timestamp = models.DateTimeField()  # Moment de la mesure
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)  # Optionnel

    def __str__(self):
        return f"{self.timestamp} | Temp={self.temperature}°C"

#commentaire
# models.py
from django.db import models
from django.contrib.auth.models import User


class Comment(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)  # Auteur du commentaire
    content = models.TextField()  # Contenu du commentaire
    created_at = models.DateTimeField(auto_now_add=True)  # Date de création
    parent = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='replies'  # Accès aux réponses via comment.replies.all()
    )

    def __str__(self):
        return f"{self.user.username}: {self.content[:30]}"


#modele pour la bande de led ws2812b
# models.py

class LEDColor(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    r = models.PositiveSmallIntegerField(default=0)  # 0-255
    g = models.PositiveSmallIntegerField(default=0)
    b = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} RGB({self.r}, {self.g}, {self.b})"



from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class Door(models.Model):
    """Représente une porte ou un point d'accès physique."""
    owner = models.ForeignKey(User, on_delete=models.CASCADE, blank=True, null=True)
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)  # ex : "porte-principale"
    actuator = models.CharField(max_length=50, blank=True, null=True)  # ex: "relay_1"
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class Badge(models.Model):
    """Badge RFID ou NFC associé à un utilisateur."""
    uid = models.CharField(max_length=100, unique=True)  # UID lu par le lecteur RFID
    owner = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    label = models.CharField(max_length=100, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.label or self.uid} ({'actif' if self.is_active else 'inactif'})"


class AccessRule(models.Model):
    """Définit qui peut accéder à quelle porte et quand."""
    badge = models.ForeignKey(Badge, on_delete=models.CASCADE)
    door = models.ForeignKey(Door, on_delete=models.CASCADE)
    allowed = models.BooleanField(default=True)

    # Restrictions temporelles
    start_time = models.TimeField(null=True, blank=True)   # ex: 08h00
    end_time = models.TimeField(null=True, blank=True)     # ex: 20h00
    start_date = models.DateField(null=True, blank=True)   # ex: 2025-01-01
    end_date = models.DateField(null=True, blank=True)     # ex: 2025-12-31
    days_of_week = models.CharField(max_length=20, blank=True, null=True,
                                    help_text="Jours autorisés (0=lundi,6=dimanche, séparés par des virgules)")

    def is_currently_valid(self):
        """Vérifie si la règle est valable à l'instant présent."""
        now = timezone.now()

        if not self.allowed:
            return False
        if self.start_date and now.date() < self.start_date:
            return False
        if self.end_date and now.date() > self.end_date:
            return False
        if self.start_time and now.time() < self.start_time:
            return False
        if self.end_time and now.time() > self.end_time:
            return False
        if self.days_of_week:
            allowed_days = [int(d) for d in self.days_of_week.split(",") if d.strip().isdigit()]
            if now.weekday() not in allowed_days:
                return False
        return True

    def __str__(self):
        return f"Règle: {self.badge} -> {self.door} ({'autorisé' if self.allowed else 'refusé'})"


class AccessLog(models.Model):
    """Historique des tentatives d'accès."""
    badge = models.ForeignKey(Badge, on_delete=models.SET_NULL, null=True, blank=True)
    uid = models.CharField(max_length=100)  # UID même si inconnu
    door = models.ForeignKey(Door, on_delete=models.SET_NULL, null=True, blank=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    allowed = models.BooleanField(default=False)
    timestamp = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    raw_payload = models.JSONField(null=True, blank=True)

    def __str__(self):
        return f"{self.timestamp} - UID:{self.uid} - Porte:{self.door} - {'OK' if self.allowed else 'REFUS'}"



#Agent alerte
class AgentAlert(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    device = models.ForeignKey(Device, on_delete=models.CASCADE, null=True, blank=True)

    code = models.CharField(max_length=100)
    message = models.CharField(max_length=255)

    level = models.CharField(
        max_length=20,
        choices=[("INFO","INFO"),("WARN","WARN"),("CRITICAL","CRITICAL")],
        default="WARN"
    )

    # ✅ AJOUTS (clé du problème)
    sensor = models.CharField(max_length=50, null=True, blank=True)
    value = models.FloatField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    def __str__(self):
        return f"[{self.level}] {self.message}"


class ActionLog(models.Model):
    """Journal des actions exécutées par l'agent (ou par des opérateurs)."""
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    action = models.CharField(max_length=100)
    details = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.created_at} - {self.user.username} - {self.action}"


class AgentConfig(models.Model):
    """Configuration par utilisateur pour l'agent (ex: cooldown alertes)."""
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    cooldown_minutes = models.PositiveIntegerField(default=10, help_text="Fenêtre d'anti-spam pour les alertes (minutes)")

    def __str__(self):
        return f"AgentConfig({self.user.username})"



#Rendre l'agent dynamique

class SensorRule(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    device = models.ForeignKey(
        Device, null=True, blank=True, on_delete=models.CASCADE
    )  # null = toutes machines

    sensor = models.CharField(max_length=50)   # "temperature", "ph", "lux"
    min_value = models.FloatField(null=True, blank=True)
    max_value = models.FloatField(null=True, blank=True)

    level = models.CharField(
        max_length=10,
        choices=[("INFO","INFO"),("WARN","WARN"),("CRITICAL","CRITICAL")]
    )

    message = models.CharField(max_length=255)
    code = models.CharField(max_length=50)

    active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.sensor} ({self.user})"


#Model de mémoire chatbot
class ChatMemory(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)

    last_device = models.ForeignKey(
        Device,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    last_sensor = models.CharField(
        max_length=50,
        null=True,
        blank=True
    )

    last_action = models.CharField(
        max_length=50,
        null=True,
        blank=True
    )

    last_message = models.TextField(
        null=True,
        blank=True
    )

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"ChatMemory({self.user.username})"
