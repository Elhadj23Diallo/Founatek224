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
        user = self.context.get('user', None)
        device_id = validated_data['device_id']
        payload = validated_data['data']
        token_key = self.context.get('token_key', '')
        # Sans utilisateur ni token, on refuse la création de device (sécurité)
        if not user and not token_key:
            raise serializers.ValidationError("Authentification requise pour créer un device ou fournir un token valide")

        # 1) tenter de trouver l'objet existant (device_id ou api_key)
        device = Device.objects.filter(device_id=device_id).first()
        if not device and token_key:
            device = Device.objects.filter(api_key=token_key).first()

        # 2) si absent : ne PAS créer automatiquement sans owner
        #    Pour des raisons de sécurité le provisioning explicite est requis
        #    (création de device via interface admin ou endpoint de provisioning).
        if not device:
            if not user:
                raise serializers.ValidationError(
                    "Device non identifié — provisioning requis avant création automatique."
                )

            try:
                with transaction.atomic():
                    defaults = {
                        "user": user,
                        "name": device_id,
                        "is_active": True,
                    }
                    if token_key:
                        defaults["api_key"] = token_key

                    device, _ = Device.objects.get_or_create(
                        device_id=device_id,
                        defaults=defaults,
                    )
            except IntegrityError:
                # retenter la récupération si insertion concurrente a échoué
                device = Device.objects.filter(device_id=device_id).first()
                if not device and token_key:
                    device = Device.objects.filter(api_key=token_key).first()

        if not device:
            raise serializers.ValidationError("Impossible de créer ou d'identifier le device")

            # Ne pas attacher automatiquement le `Device` à l'utilisateur ici.
            # L'attribution doit être faite via un provisioning explicite pour
            # éviter les collisions quand plusieurs utilisateurs sont connectés.

        # 3) création de l'AppareilData
        return AppareilData.objects.create(
            device=device,
            payload=payload
        )
# ...existing code...