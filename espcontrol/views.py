from rest_framework.response import Response
from rest_framework.decorators import api_view
from .models import LED
from .serializers import LEDSerializer
from django.http import JsonResponse
from .models import DHTData  # Importer le modèle DHTData
from django.shortcuts import render, redirect
from .models import LED
from rest_framework.views import APIView
from rest_framework.response import Response
from django.core.files.base import ContentFile
from .models import UploadedImage
import base64
from io import BytesIO
from PIL import Image
import requests
from django.contrib.auth import logout


def home(request):
    return render(request, 'espcontrol/home.html')



from rest_framework import status
from .models import Comptage
from .serializers import ComptageSerializer

# ----------------------------------
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

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
            esp_ip = 'http://192.168.167.246/reset'  # 🔁 Change cette IP si besoin
            requests.get(esp_ip, timeout=3)
        except requests.exceptions.RequestException as e:
            print("Erreur lors de la communication avec l'ESP:", e)

        return redirect('dashboard')

    comptages = Comptage.objects.all().order_by('-timestamp')[:5]
    return render(request, 'espcontrol/deleteComp.html', {'comptage': comptages})

# surveillance/views.py

class ImageUploadView(APIView):
    def post(self, request, *args, **kwargs):
        # Récupérer l'image encodée en base64
        image_data = request.data.get('image', None)
        if not image_data:
            return Response({"error": "No image provided"}, status=400)

        # Décoder l'image
        img_data = base64.b64decode(image_data)
        img = Image.open(BytesIO(img_data))

        # Convertir l'image en format qui peut être enregistré
        img_io = BytesIO()
        img.save(img_io, 'JPEG')
        img_io.seek(0)

        # Sauvegarder l'image dans le modèle
        uploaded_image = UploadedImage.objects.create(
            image=ContentFile(img_io.read(), 'received_image.jpg')
        )

        return Response({"message": "Image reçue et enregistrée avec succès", "image_id": uploaded_image.id}, status=200)



@api_view(['GET'])
def led_status(request):
    led = LED.objects.first()
    serializer = LEDSerializer(led)
    return Response(serializer.data)


##Vue pour afficher l'etat de la LED

def led_control(request):
    led, created = LED.objects.get_or_create(pk=1)  # s'assure qu'une LED existe

    if request.method == 'POST':
        led.etat = not led.etat  # inverse l'état actuel
        led.save()

    return render(request, 'espcontrol/led_control.html', {'led_status': led.etat})


## Vue pour recuperer les données de température et d'hymidité

def dht_data(request):
    temperature = request.GET.get('temperature')
    humidity = request.GET.get('humidity')

    if temperature and humidity:
        DHTData.objects.create(
            temperature=float(temperature),
            humidity=float(humidity)
        )
        print(f"Température: {temperature} °C, Humidité: {humidity} %")
        return JsonResponse({'temperature': temperature, 'humidity': humidity})
    else:
        # Récupère les 10 dernières données (du plus récent au plus ancien)
        dht_data = DHTData.objects.all().order_by('-created_at')[:10]  # ou selon le nom de ton champ date

        # Convertir le QuerySet en liste (pas obligatoire mais utile pour indexer)
        dht_data = list(dht_data)

        return render(request, 'espcontrol/dht_data.html', {
            'dht_data': dht_data
        })
    

# Vue pour le système d'irrigation automatique
def irrigation_auto(request):
    return render(request, 'espcontrol/irrigation_auto.html')

# Vue pour la poubelle intelligente
def poubelle_intelligente(request):
    return render(request, 'espcontrol/poubelle_intelligente.html')

# Vue pour le système de surveillance
def systeme_surveillance(request):
    # Logique pour récupérer les données ou afficher des informations liées à la surveillance
    return render(request, 'espcontrol/systeme_surveillance.html')

def controle_appareils(request):
    return render(request, 'espcontrol/controle_appareils.html')


