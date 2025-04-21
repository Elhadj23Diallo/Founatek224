from rest_framework import serializers
from .models import LED, Relais, Comptage

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
