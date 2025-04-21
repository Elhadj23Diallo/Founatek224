from rest_framework import serializers
from .models import LED

class LEDSerializer(serializers.ModelSerializer):
    class Meta:
        model = LED
        fields = ['etat']


from .models import Comptage

class ComptageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Comptage
        fields = ['id', 'compteur', 'timestamp']

from .models import GasData

class GasDataSerializer(serializers.ModelSerializer):
    class Meta:
        model = GasData
        fields = ['id', 'ppm', 'gaz_type', 'timestamp']  # secret_key non requis ici si c'est juste pour validation
