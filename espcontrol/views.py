from django.shortcuts import render, redirect, get_object_or_404

from django.http import JsonResponse
from django.contrib.auth import logout
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

from .models import LED, DHTData, UploadedImage, Comptage, SoilData
from .serializers import LEDSerializer, ComptageSerializer

# Pour gestion d'image
from django.core.files.base import ContentFile
import base64
from io import BytesIO
from PIL import Image
import requests


from django.http import JsonResponse

def home(request):
    return render(request, 'espcontrol/home.html')


class CompteurDataAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Exemple de retour de données protégées
        return Response({"message": "Voici les données du capteur."})


def login_page(request):
    return render(request, 'espcontrol/login.html')


def logout_view(request):
    logout(request)
    return redirect('login')

#Vue pour le comptage d'objets
# APIView pour GET et POST
class ComptageAPIView(APIView):

    def get(self, request):
        comptages = Comptage.objects.all().order_by('-timestamp')[:10]
        serializer = ComptageSerializer(comptages, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = ComptageSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# Dashboard
def dashboard(request):
    comptages = Comptage.objects.all().order_by('-timestamp')[:5]
    return render(request, 'espcontrol/dashboard.html', {'comptages': comptages})

def initCompteur(request):
    if request.method == 'POST' and 'reset' in request.POST:
        # 1. Réinitialiser la BDD
        Comptage.objects.all().delete()

        # 2. Envoyer la commande à l'ESP pour qu'il remette son compteur à zéro
        try:
            esp_ip = 'http://192.168.167.93/reset'  # 🔁 Change cette IP si besoin
            requests.get(esp_ip, timeout=3)
        except requests.exceptions.RequestException as e:
            print("Erreur lors de la communication avec l'ESP:", e)

        return redirect('dashboard')

    comptages = Comptage.objects.all().order_by('-timestamp')[:5]
    return render(request, 'espcontrol/deleteComp.html', {'comptage': comptages})

# surveillance/views.py

class ImageUploadView(APIView):
    def post(self, request, *args, **kwargs):
        image_data = request.data.get('image', None)
        if not image_data:
            return Response({"error": "No image provided"}, status=400)

        try:
            # Décodage de l'image base64
            img_data = base64.b64decode(image_data)
            img = Image.open(BytesIO(img_data))
            img_io = BytesIO()
            img.save(img_io, 'JPEG')
            img_io.seek(0)

            uploaded_image = UploadedImage.objects.create(
                image=ContentFile(img_io.read(), 'received_image.jpg')
            )

            return Response({
                "message": "Image reçue et enregistrée avec succès",
                "image_id": uploaded_image.id
            }, status=200)

        except Exception as e:
            return Response({"error": str(e)}, status=500)

def systeme_surveillance(request):
    images = UploadedImage.objects.all()  # Récupère toutes les images stockées.
    return render(request, 'espcontrol/surveillance.html', {'images': images})

def get_latest_image(request):
    # Récupérer la dernière image
    image = UploadedImage.objects.all().order_by('-created_at').first()
    if image:
        image_url = image.image.url
        return JsonResponse({'image_url': image_url})
    else:
        return JsonResponse({'image_url': None})



@api_view(['GET'])
def led_status(request):
    led = LED.objects.first()
    serializer = LEDSerializer(led)
    return Response(serializer.data)



##Vue pour afficher l'etat de la LED

""" def led_control(request):
    led, created = LED.objects.get_or_create(pk=1)  # s'assure qu'une LED existe

    if request.method == 'POST':
        led.etat = not led.etat  # inverse l'état actuel
        led.save()

    return render(request, 'espcontrol/irrigation.html', {'led_status': led.etat}) """


## Vue pour recuperer les données de température et d'hymidité

from django.http import JsonResponse
from django.shortcuts import render, redirect
from .models import DHTData, LED

""" def led_control(request):
    # Récupérer l'état de la LED
    led, created = LED.objects.get_or_create(pk=1)  # S'assure qu'une LED existe

    # Si une requête POST est reçue, on inverse l'état de la LED
    if request.method == 'POST':
        led.etat = not led.etat  # Inverse l'état actuel
        led.save()
        return redirect('dht-data/')  # Rediriger vers la même page après la mise à jour

    # Récupérer les données du capteur via les paramètres GET
    temperature = request.GET.get('temperature')
    humidity = request.GET.get('humidity')

    # Si des données de température et d'humidité sont présentes
    if temperature and humidity:
        try:
            # Enregistrer les nouvelles données dans la base
            DHTData.objects.create(
                temperature=float(temperature),
                humidity=float(humidity)
            )
            print(f"Température: {temperature} °C, Humidité: {humidity} %")

            # Retourner les données au format JSON
            return JsonResponse({'temperature': temperature, 'humidity': humidity})

        except ValueError:
            # Si les valeurs ne sont pas valides (ex: conversion échouée), retourner une erreur
            return JsonResponse({'error': 'Valeurs invalides'}, status=400)

    else:
        # Récupérer les 10 dernières données (du plus récent au plus ancien)
        dht_data = DHTData.objects.all().order_by('-created_at')[:10]

        # Convertir le QuerySet en liste (facultatif mais utile)
        dht_data = list(dht_data)

        # Renvoyer les données à la vue sous forme de contexte
        return render(request, 'espcontrol/led_control.html', {
            'dht_data': dht_data,
            'led_status': led.etat  # Passer l'état de la LED à la vue
        })
 """

def led_control(request):
    # Récupérer l'état de la LED
    led, created = LED.objects.get_or_create(pk=1)  # S'assure qu'une LED existe

    # Si une requête POST est reçue, on inverse l'état de la LED
    if request.method == 'POST':
        led.etat = not led.etat  # Inverse l'état actuel
        led.save()
        return redirect('dht-data/')  # Rediriger vers la même page après la mise à jour

    # Récupérer les données du capteur via les paramètres GET
    temperature = request.GET.get('temperature')
    humidity = request.GET.get('humidity')

    # Si des données de température et d'humidité sont présentes
    if temperature and humidity:
        try:
            # Enregistrer les nouvelles données dans la base
            DHTData.objects.create(
                temperature=float(temperature),
                humidity=float(humidity)
            )
            print(f"Température: {temperature} °C, Humidité: {humidity} %")

            # Envoi de mail si la température dépasse un certain seuil
            if float(temperature) > 30:  # Seuil de température (30°C par exemple)
                send_mail(
                    'Alerte : Température élevée',
                    f'La température actuelle est de {temperature} °C, ce qui est au-dessus du seuil de 30°C. Pensez à alumer la clim.',
                    settings.EMAIL_HOST_USER,  # Expéditeur (Doit être configuré dans settings.py)
                    ['isaacdiallo30@gmail.com'],  # Liste des destinataires
                    fail_silently=False,
                )

            # Retourner les données au format JSON
            return JsonResponse({'temperature': temperature, 'humidity': humidity})

        except ValueError:
            # Si les valeurs ne sont pas valides (ex: conversion échouée), retourner une erreur
            return JsonResponse({'error': 'Valeurs invalides'}, status=400)

    else:
        # Récupérer les 10 dernières données (du plus récent au plus ancien)
        dht_data = DHTData.objects.all().order_by('-created_at')[:10]

        # Convertir le QuerySet en liste (facultatif mais utile)
        dht_data = list(dht_data)

        # Renvoyer les données à la vue sous forme de contexte
        return render(request, 'espcontrol/led_control.html', {
            'dht_data': dht_data,
            'led_status': led.etat  # Passer l'état de la LED à la vue
        })

# Vue pour le système d'irrigation automatique
def irrigation_auto(request):
    return render(request, 'espcontrol/irrigation_auto.html')

# Vue pour la poubelle intelligente
def poubelle_intelligente(request):
    return render(request, 'espcontrol/poubelle_intelligente.html')




ESP8266_IP = "http://192.168.167.93"  # Remplace par l'IP réelle de ton ESP8266

from rest_framework.decorators import api_view
from rest_framework.response import Response
from .models import Relais
from .serializers import RelaisSerializer

@api_view(['GET', 'PUT'])
def relais_status(request, relais_num):
    try:
        relais = Relais.objects.get(num=relais_num)  # Trouver le relais par son numéro
    except Relais.DoesNotExist:
        return Response({"message": "Relais non trouvé"}, status=status.HTTP_404_NOT_FOUND)

    if request.method == 'GET':
        # Sérialisation des données du relais
        serializer = RelaisSerializer(relais)
        return Response(serializer.data)

    elif request.method == 'PUT':
        # Mettre à jour l'état du relais
        etat = request.data.get('etat', None)

        # Valider l'état reçu
        if etat is None:
            return Response({"message": "L'état du relais est requis"}, status=status.HTTP_400_BAD_REQUEST)

        # Si l'état est valide (True/False ou 'on'/'off')
        if etat in ['on', 'off']:
            relais.etat = True if etat == 'on' else False
        elif isinstance(etat, bool):
            relais.etat = etat
        else:
            return Response({"message": "État invalide. Utilisez 'on' ou 'off'."}, status=status.HTTP_400_BAD_REQUEST)

        relais.save()  # Sauvegarde l'état dans la base de données
        return Response({"message": "État du relais mis à jour", "etat": relais.etat}, status=status.HTTP_200_OK)





from django.shortcuts import render
from .models import Relais

def relais_control(request, relais_num):
    # Récupère le relais avec l'ID spécifique
    relais = get_object_or_404(Relais, num=relais_num)

    if request.method == 'POST':
        # Inverse l'état du relais lorsqu'on appuie sur le bouton
        relais.etat = not relais.etat
        relais.save()

    return render(request, 'espcontrol/relais_control.html', {'relais': relais})


#capteur de température et d'humidité du sol
# Fonction pour traiter les données du capteur d'humidité du sol
def soil_data(request):
    # Lire l'humidité envoyée par le capteur
    humidity = request.GET.get('humidity')

    # Afficher l'humidité reçue dans les logs pour déboguer
    print(f"Received humidity: {humidity}")

    # Vérifier si l'humidité a bien été reçue et si elle peut être convertie en entier
    if humidity is not None:
        try:
            humidity = int(humidity)  # Convertir en entier explicitement
        except ValueError:
            return JsonResponse({'status': 'error', 'message': 'Invalid humidity value'}, status=400)

        # Sauvegarder les données d'humidité dans la base de données
        soil_data = SoilData(humidity=humidity)
        soil_data.save()

        # Vérifier si l'humidité dépasse un seuil critique (par exemple, si elle est trop faible)
        if humidity < 30:  # Seuil d'humidité critique
            send_mail(
                'Alerte : Humidité du sol faible',
                f'L\'humidité actuelle du sol est de {humidity}%, ce qui est en dessous du seuil critique de 30%. Pensez à arroser vos plantes.',
                settings.EMAIL_HOST_USER,  # Expéditeur (Doit être configuré dans settings.py)
                ['isaacdiallo30@gmail.com'],  # Liste des destinataires
                fail_silently=False,
            )

        # Retourner une réponse JSON avec le statut de succès
        return JsonResponse({'status': 'success', 'humidity': humidity})
    else:
        return JsonResponse({'status': 'error', 'message': 'Missing humidity data'}, status=400)


def display_soil_data(request):
    # Récupérer toutes les données d'humidité
    data = SoilData.objects.all().order_by('-created_at')  # Trier par date décroissante

    # Passer les données au template
    return render(request, 'espcontrol/soil_data.html', {'data': data})
