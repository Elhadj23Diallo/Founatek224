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
