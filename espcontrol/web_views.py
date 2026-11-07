from datetime import datetime, timedelta
import time

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.db import connection
from django.db.models import Avg, Max, Min, OuterRef, Subquery
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .forms import RelaisForm
from .models import (
    ActionLog,
    AppareilData,
    Comptage,
    DHTData,
    Device,
    LED,
    NtcSensorData,
    Relais,
    SensorData,
    SoilData,
)


def vitrine(request):
    """Page vitrine publique — pas de @login_required, c'est la première
    chose que voit un visiteur non connecté."""
    if request.user.is_authenticated:
        return redirect("home")
    return render(request, "espcontrol/vitrine.html")


@login_required
def home(request):
    return render(request, "espcontrol/home.html")


@login_required
def device_center(request):
    """Centre de santé des appareils; affiche uniquement les appareils du compte connecté."""
    cutoff = timezone.now() - timedelta(minutes=5)
    latest_records = AppareilData.objects.filter(
        device_id=OuterRef("pk")
    ).order_by("-received_at")
    devices = list(
        Device.objects.filter(user=request.user)
        .annotate(
            latest_payload=Subquery(latest_records.values("payload")[:1]),
            latest_data_at=Subquery(latest_records.values("received_at")[:1]),
        )
        .order_by("name", "device_id")
    )

    for device in devices:
        contact_times = [
            value for value in (device.last_seen, device.latest_data_at) if value
        ]
        device.last_contact = max(contact_times) if contact_times else None
        device.is_online = bool(
            device.is_active and device.last_contact and device.last_contact >= cutoff
        )
        payload = device.latest_payload if isinstance(device.latest_payload, dict) else {}
        device.latest_metrics = [
            (str(key), str(value)) for key, value in list(payload.items())[:6]
        ]

    online_count = sum(1 for device in devices if device.is_online)
    return render(
        request,
        "espcontrol/device_center.html",
        {
            "devices": devices,
            "device_count": len(devices),
            "online_count": online_count,
            "offline_count": len(devices) - online_count,
            "online_window_minutes": 5,
        },
    )


@login_required
def led_rgb_control_page(request):
    return render(request, "espcontrol/led_rgb_control.html")


@login_required
def led_control(request):
    led = LED.objects.first()
    if request.method == "POST":
        temperature = request.POST.get("temperature")
        humidity = request.POST.get("humidity")
        try:
            DHTData.objects.create(
                temperature=float(temperature),
                humidity=float(humidity),
                user=request.user,
            )
            if float(temperature) > 18:
                send_mail(
                    "Alerte : Température élevée",
                    f"Température actuelle : {temperature} °C. Pensez à allumer la clim.",
                    settings.EMAIL_HOST_USER,
                    ["isaacdiallo30@gmail.com"],
                    fail_silently=False,
                )
            return JsonResponse({"temperature": temperature, "humidity": humidity})
        except (TypeError, ValueError):
            return JsonResponse({"error": "Valeurs invalides"}, status=400)

    dht_data = DHTData.objects.filter(user=request.user).order_by("-created_at")[:10]
    return render(
        request,
        "espcontrol/led_control.html",
        {"dht_data": dht_data, "led_status": led.etat if led else False},
    )


@login_required
def irrigation_auto(request):
    return render(request, "espcontrol/irrigation_auto.html")


@login_required
def poubelle_intelligente(request):
    return render(request, "espcontrol/poubelle_intelligente.html")


@login_required
def dashboard(request):
    comptages = Comptage.objects.filter(user=request.user).order_by("-timestamp")[:5]
    return render(request, "espcontrol/dashboard.html", {"comptages": comptages})


@login_required
def comptage_live(request):
    comptages = Comptage.objects.filter(user=request.user).order_by("-timestamp")[:20]
    data = [
        {
            "id": c.id,
            "compteur": c.compteur,
            "timestamp": c.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
        }
        for c in comptages
    ]
    return JsonResponse(data, safe=False)


@login_required
def initCompteur(request):
    if request.method == "POST" and "reset" in request.POST:
        Comptage.objects.filter(user=request.user).delete()
        time.sleep(0.3)
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM sqlite_sequence WHERE name='espcontrol_comptage';")
        messages.success(request, "Compteur réinitialisé avec succès !")
        return redirect("dashboard")

    comptages = Comptage.objects.filter(user=request.user).order_by("-timestamp")[:5]
    return render(request, "espcontrol/deleteComp.html", {"comptage": comptages})


@login_required
def control_relais(request):
    if request.method == "POST":
        form = RelaisForm(request.POST)
        if form.is_valid():
            relais = form.save(commit=False)
            relais.user = request.user
            try:
                relais.save()
                return redirect("afficher_relais")
            except Exception:
                form.add_error("num", "Ce numéro est déjà utilisé par vous.")
    else:
        form = RelaisForm()

    return render(request, "espcontrol/control_relais.html", {"form": form})


@login_required
def afficher_relais(request):
    relais = Relais.objects.filter(user=request.user)
    recent_actions = ActionLog.objects.filter(
        user=request.user, action="RELAY_STATE_REQUESTED"
    ).order_by("-created_at")[:10]
    return render(
        request,
        "espcontrol/relais.html",
        {"relais": relais, "recent_actions": recent_actions},
    )


@login_required
@require_POST
def toggle_relais(request, num):
    relais = get_object_or_404(Relais, num=num, user=request.user)
    previous_state = relais.etat
    relais.etat = not relais.etat
    relais.save(update_fields=["etat"])
    ActionLog.objects.create(
        user=request.user,
        action="RELAY_STATE_REQUESTED",
        details={
            "source": "web",
            "relay_num": relais.num,
            "relay_name": relais.nom,
            "previous_state": "on" if previous_state else "off",
            "requested_state": "on" if relais.etat else "off",
        },
    )
    messages.success(
        request,
        "La demande a été enregistrée dans Founatek; l’exécution physique n’est pas confirmée par cette page.",
    )
    return redirect("afficher_relais")


@login_required
def display_soil_data(request):
    data = SoilData.objects.filter(user=request.user).order_by("-created_at")
    return render(request, "espcontrol/soil_data.html", {"data": data})


@login_required
def view_ntc_data(request):
    data_list = NtcSensorData.objects.filter(user=request.user).order_by("timestamp")
    last_temp = data_list.last() if data_list.exists() else None
    max_temp = data_list.aggregate(Max("temperature"))["temperature__max"] if data_list.exists() else None
    min_temp = data_list.aggregate(Min("temperature"))["temperature__min"] if data_list.exists() else None

    labels_sec = []
    temps = []
    if data_list.exists():
        t0 = data_list.first().timestamp
        for d in data_list:
            labels_sec.append(int((d.timestamp - t0).total_seconds()))
            temps.append(d.temperature)

    context = {
        "data_list": data_list,
        "last_temp": last_temp,
        "max_temp": max_temp,
        "min_temp": min_temp,
        "labels_sec": labels_sec,
        "temps": temps,
    }
    return render(request, "espcontrol/ntc_data.html", context)


@login_required
def gas_data_view(request):
    data = SensorData.objects.filter(user=request.user).order_by("-timestamp")
    stats = data.aggregate(
        avg_temp=Avg("temperature"),
        min_temp=Min("temperature"),
        max_temp=Max("temperature"),
        avg_hum=Avg("humidity"),
        min_hum=Min("humidity"),
        max_hum=Max("humidity"),
        avg_co2=Avg("co2"),
        min_co2=Min("co2"),
        max_co2=Max("co2"),
    )
    return render(request, "espcontrol/gas_data.html", {"data": data, "stats": stats})


@login_required
def menu_page(request):
    return render(request, "espcontrol/menu_page.html")
