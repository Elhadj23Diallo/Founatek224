#Import
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth import logout
from django.conf import settings
from django.core.mail import send_mail
from django.core.files.base import ContentFile
from django.contrib.auth.decorators import login_required
from rest_framework.views import APIView
from rest_framework.response import Response
from .utils import api_permission_required
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import api_view
from rest_framework import generics

from .models import LED, DHTData, UploadedImage, Comptage, SoilData, GasData
from .serializers import LEDSerializer, ComptageSerializer, GasDataSerializer

import base64
from io import BytesIO
from PIL import Image
import requests

from .utils import api_permission_required


#🏠 Pages de base
@login_required
def home(request):
    user = request.user
    is_abonne = user.groups.filter(name='Abonné').exists() 
    return render(request, 'espcontrol/home.html', {'is_abonne': is_abonne})

from django.contrib import messages

#📊 Dashboard & Comptage
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


def dashboard(request):
    comptages = Comptage.objects.all().order_by('-timestamp')[:5]
    return render(request, 'espcontrol/dashboard.html', {'comptages': comptages})


def initCompteur(request):
    if request.method == 'POST' and 'reset' in request.POST:
        Comptage.objects.all().delete()
        try:
            requests.get('http://192.168.167.93/reset', timeout=3)
        except requests.exceptions.RequestException as e:
            print("Erreur ESP:", e)
        return redirect('dashboard')

    comptages = Comptage.objects.all().order_by('-timestamp')[:5]
    return render(request, 'espcontrol/deleteComp.html', {'comptage': comptages})


#🌡️ Température, Humidité, LED & Alerte Mail
@api_permission_required
def led_control(request):
    led, _ = LED.objects.get_or_create(pk=1)

    if request.method == 'POST':
        led.etat = not led.etat
        led.save()
        return redirect('dht-data')

    temperature = request.GET.get('temperature')
    humidity = request.GET.get('humidity')
    print(f"Temperature: {temperature}, Humidity: {humidity}")  # Debug ici

    if temperature and humidity:
        try:
            DHTData.objects.create(
                temperature=float(temperature),
                humidity=float(humidity)
            )

            if float(temperature) > 18:
                send_mail(
                    'Alerte : Température élevée',
                    f'Température actuelle : {temperature} °C. Pensez à allumer la clim.',
                    settings.EMAIL_HOST_USER,
                    ['isaacdiallo30@gmail.com'],
                    fail_silently=False,
                )

            return JsonResponse({'temperature': temperature, 'humidity': humidity})
        except ValueError:
            return JsonResponse({'error': 'Valeurs invalides'}, status=400)
    
    dht_data = DHTData.objects.all().order_by('-created_at')[:10]
    return render(request, 'espcontrol/led_control.html', {
        'dht_data': dht_data,
        'led_status': led.etat
    })

#💡 LED API
@api_permission_required
@api_view(['GET'])
def led_status(request):
    led = LED.objects.first()
    serializer = LEDSerializer(led)
    return Response(serializer.data)

#🌿 Irrigation & Autres interfaces
@api_permission_required
def irrigation_auto(request):
    return render(request, 'espcontrol/irrigation_auto.html')

@api_permission_required
def poubelle_intelligente(request):
    return render(request, 'espcontrol/poubelle_intelligente.html')

@api_permission_required
def control_relais(request):
    return render(request, 'espcontrol/control_relais.html')


#🔌 Contrôle Relais via ESP8266

ESP8266_IP = "http://192.168.167.93"

@api_permission_required
def toggle_relais(request, relais_num):
    try:
        url = f"{ESP8266_IP}/relais/{relais_num}/toggle"
        response = requests.get(url)

        if response.status_code == 200:
            return JsonResponse({'status': 'success', 'message': f'Relais {relais_num} contrôlé'})
        else:
            return JsonResponse({'status': 'error', 'message': 'Erreur ESP'}, status=500)

    except requests.exceptions.RequestException as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

#📸 Système de surveillance – upload & affichage image
@api_permission_required
class ImageUploadView(APIView):
    def post(self, request, *args, **kwargs):
        image_data = request.data.get('image', None)
        if not image_data:
            return Response({"error": "No image provided"}, status=400)

        try:
            img_data = base64.b64decode(image_data)
            img = Image.open(BytesIO(img_data))
            img_io = BytesIO()
            img.save(img_io, 'JPEG')
            img_io.seek(0)

            uploaded_image = UploadedImage.objects.create(
                image=ContentFile(img_io.read(), 'received_image.jpg')
            )

            return Response({
                "message": "Image enregistrée avec succès",
                "image_id": uploaded_image.id
            }, status=200)

        except Exception as e:
            return Response({"error": str(e)}, status=500)

@api_permission_required
def systeme_surveillance(request):
    images = UploadedImage.objects.all()
    return render(request, 'espcontrol/surveillance.html', {'images': images})

@api_permission_required
def get_latest_image(request):
    image = UploadedImage.objects.all().order_by('-created_at').first()
    if image:
        return JsonResponse({'image_url': image.image.url})
    return JsonResponse({'image_url': None})


#Vue pour le capteur de gaz
from rest_framework import generics, status
from rest_framework.response import Response
from .models import GasData
from .serializers import GasDataSerializer

API_SECRET_KEY = "@Founatek_2025_SECURITY_KEY!"  # clé à vérifier

class GasDataListCreateView(generics.ListCreateAPIView):
    queryset = GasData.objects.all().order_by('-timestamp')
    serializer_class = GasDataSerializer

    def create(self, request, *args, **kwargs):
        # Récupère la clé secrète dans les données
        secret_key = request.data.get("secret_key")

        if secret_key != API_SECRET_KEY:
            return Response({"error": "Clé API invalide ou manquante"}, status=status.HTTP_403_FORBIDDEN)

        # Supprime la clé avant d’enregistrer les données
        mutable_data = request.data.copy()
        mutable_data.pop("secret_key", None)

        serializer = self.get_serializer(data=mutable_data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)

        return Response(serializer.data, status=status.HTTP_201_CREATED)

#vue pour afficher les données du capteur de gaz

def gas_data_view(request):
    gas_data = GasData.objects.all().order_by('-timestamp')  # par exemple
    return render(request, 'espcontrol/gas_data.html', {'gas_data': gas_data})

#🌱 Données Capteur d’Humidité du Sol (à compléter)

@api_permission_required
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
        print(f"New DHTData created with Temperature: Humidity: {humidity}")
        # Retourner une réponse JSON avec le statut de succès
        return JsonResponse({'status': 'success', 'humidity': humidity})
    else:
        return JsonResponse({'status': 'error', 'message': 'Missing humidity data'}, status=400)

#🔒 API sécurisée d’exemple
@api_permission_required
class CompteurDataAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({"message": "Voici les données du capteur."})


@api_permission_required
def display_soil_data(request):
    # Récupérer toutes les données d'humidité
    data = SoilData.objects.all().order_by('-created_at')  # Trier par date décroissante

    # Passer les données au template
    return render(request, 'espcontrol/soil_data.html', {'data': data})



class CompteurDataAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Exemple de retour de données protégées
        return Response({"message": "Voici les données du capteur."})
    
@api_permission_required 
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
    