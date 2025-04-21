from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth import logout
from django.conf import settings
from django.core.mail import send_mail
from django.core.files.base import ContentFile
from django.contrib.auth.decorators import login_required
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework import generics

from .models import LED, DHTData, UploadedImage, Comptage, SoilData, GasData
from .serializers import LEDSerializer, ComptageSerializer, GasDataSerializer

import base64
from io import BytesIO
from PIL import Image
import requests

# Pages de base
@login_required
def home(request):
    return render(request, 'espcontrol/home.html')

def login_page(request):
    return render(request, 'espcontrol/login.html')

@login_required
def logout_view(request):
    logout(request)
    return redirect('login')

# Dashboard & Comptage
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

# LED Control & Température/Humidité
@api_view(['POST'])
def led_control(request):
    led, _ = LED.objects.get_or_create(pk=1)

    if request.method == 'POST':
        led.etat = not led.etat
        led.save()
        return redirect('dht-data/')

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

# LED API
@api_view(['GET'])
def led_status(request):
    led = LED.objects.first()
    serializer = LEDSerializer(led)
    return Response(serializer.data)

# Surveillance System (Image upload & display)
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

def systeme_surveillance(request):
    images = UploadedImage.objects.all()
    return render(request, 'espcontrol/surveillance.html', {'images': images})

def get_latest_image(request):
    image = UploadedImage.objects.all().order_by('-created_at').first()
    if image:
        return JsonResponse({'image_url': image.image.url})
    return JsonResponse({'image_url': None})

# Gas Sensor Data API
class GasDataListCreateView(generics.ListCreateAPIView):
    queryset = GasData.objects.all().order_by('-timestamp')
    serializer_class = GasDataSerializer

    def create(self, request, *args, **kwargs):
        secret_key = request.data.get("secret_key")

        if secret_key != API_SECRET_KEY:
            return Response({"error": "Clé API invalide ou manquante"}, status=status.HTTP_403_FORBIDDEN)

        mutable_data = request.data.copy()
        mutable_data.pop("secret_key", None)

        serializer = self.get_serializer(data=mutable_data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)

        return Response(serializer.data, status=status.HTTP_201_CREATED)

def gas_data_view(request):
    gas_data = GasData.objects.all().order_by('-timestamp')
    return render(request, 'espcontrol/gas_data.html', {'gas_data': gas_data})

# Soil Humidity Data
@api_permission_required
def soil_data(request):
    humidity = request.GET.get('humidity')

    if humidity is not None:
        try:
            humidity = int(humidity)
        except ValueError:
            return JsonResponse({'status': 'error', 'message': 'Invalid humidity value'}, status=400)

        soil_data = SoilData(humidity=humidity)
        soil_data.save()

        if humidity < 30:
            send_mail(
                'Alerte : Humidité du sol faible',
                f'L\'humidité actuelle du sol est de {humidity}%, ce qui est en dessous du seuil critique de 30%. Pensez à arroser vos plantes.',
                settings.EMAIL_HOST_USER,
                ['isaacdiallo30@gmail.com'],
                fail_silently=False,
            )

        return JsonResponse({'status': 'success', 'humidity': humidity})
    else:
        return JsonResponse({'status': 'error', 'message': 'Missing humidity data'}, status=400)

def display_soil_data(request):
    data = SoilData.objects.all().order_by('-created_at')
    return render(request, 'espcontrol/soil_data.html', {'data': data})

# Secure API example
@api_permission_required
class CompteurDataAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({"message": "Voici les données du capteur."})
