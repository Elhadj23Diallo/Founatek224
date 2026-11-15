from rest_framework import serializers
from .models import LED, Relais, Comptage, UploadedImage, Device, AppareilData

class LEDSerializer(serializers.ModelSerializer):
    class Meta:
        model = LED
        fields = ['etat']


class RelaisSerializer(serializers.ModelSerializer):
    class Meta:
        model = Relais
        fields = ['num', 'etat']  # Nous incluons le numéro et l'état du relais



class ComptageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Comptage
        fields = ['id', 'compteur', 'timestamp']

from .models import SensorData

class SensorDataSerializer(serializers.ModelSerializer):
    class Meta:
        model = SensorData
        fields = ['id', 'temperature', 'humidity', 'co2', 'timestamp', 'gaz_type', 'user']  # Ajouter 'user' pour associer l'utilisateur
        read_only_fields = ['user']  # Rendre 'user' en lecture seule car l'utilisateur est défini automatiquement lors de la création



class UploadedImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = UploadedImage
        fields = ['id', 'image', 'created_at']



# ...existing code...
from django.db import IntegrityError, transaction
# ...existing code...



class AppareilDataSerializer(serializers.Serializer):
    device_id = serializers.CharField(max_length=100)
    data = serializers.JSONField()

    def validate_device_id(self, value):
        if not value:
            raise serializers.ValidationError("device_id ne peut pas être vide")
        return value

    def create(self, validated_data):
        user = self.context.get("user")
        token_key = self.context.get("token_key")
        device_id = validated_data["device_id"]
        payload = validated_data["data"]

        if not user:
            raise serializers.ValidationError("Utilisateur non authentifié")

        # 🔒 Limite d'appareils du plan : seulement pour un device_id jamais vu
        # chez cet utilisateur (un device déjà connu peut toujours envoyer des mesures).
        if not user.is_superuser and not Device.objects.filter(device_id=device_id, user=user).exists():
            from monetisation.utils import check_device_quota
            device_ok, device_count, max_devices = check_device_quota(user)
            if not device_ok:
                from rest_framework.exceptions import PermissionDenied
                raise PermissionDenied(
                    f"Limite d'appareils atteinte pour votre plan ({device_count}/{max_devices}). "
                    "Passez à un plan supérieur pour connecter un nouvel appareil."
                )

        # 🔥 1. CRÉATION AUTO SÉCURISÉE PAR USER
        with transaction.atomic():
            device, created = Device.objects.get_or_create(
                device_id=device_id,
                user=user,
                defaults={
                    "name": f"Device {device_id}",
                    "is_active": True,
                    "api_key": token_key
                }
            )

        # 🔥 2. AUTO-ENRICHISSEMENT INTELLIGENT
        updated = False

        # 👉 Type auto
        if payload:
            if "pm2p5" in payload or "pm10" in payload:
                if getattr(device, "type", None) != "air_quality":
                    device.type = "air_quality"
                    updated = True

            elif "soil_moisture" in payload:
                device.type = "agriculture"
                updated = True

            elif "temperature" in payload and "humidity" in payload:
                device.type = "environment"
                updated = True

        # 👉 Géolocalisation
        if payload.get("latitude") and payload.get("longitude"):
            device.latitude = payload.get("latitude")
            device.longitude = payload.get("longitude")
            updated = True

        # 👉 Dernière activité
        from django.utils import timezone
        device.last_seen = timezone.now()
        updated = True

        if updated:
            device.save()

        # 🔥 3. SAUVEGARDE DATA
        return AppareilData.objects.create(
            device=device,
            payload=payload
        )