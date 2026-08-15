# 🔬 Founatek Oscilloscope — Guide d'installation complet

## 1. Ajouter l'application dans ton projet Founatek existant

### Copier le dossier
Copie le dossier `oscilloscope/` dans la racine de ton projet Django
(au même niveau que `espcontrol/`, `monetisation/`, etc.)

---

## 2. Modifier `settings.py`

Dans `INSTALLED_APPS`, ajoute :
```python
INSTALLED_APPS = [
    ...
    'oscilloscope',
]
```

Assure-toi que `numpy` est installé :
```python
# Dans requirements.txt ou via pip
numpy
```

---

## 3. Modifier `urls.py` (fichier principal du projet)

```python
from django.urls import path, include

urlpatterns = [
    ...
    path('oscilloscope/', include('oscilloscope.urls', namespace='oscilloscope')),
]
```

---

## 4. Installer les dépendances

```bash
pip install numpy --break-system-packages
pip install djangorestframework --break-system-packages  # si pas déjà installé
```

---

## 5. Migrations

```bash
python manage.py makemigrations oscilloscope
python manage.py migrate
```

---

## 6. Tester localement

```bash
python manage.py runserver
```

Ouvre : http://127.0.0.1:8000/oscilloscope/

---

## 7. Déploiement sur PythonAnywhere

1. Upload le dossier `oscilloscope/` via l'interface Files
2. Dans la console Bash PythonAnywhere :
```bash
pip install numpy --user
python manage.py makemigrations oscilloscope
python manage.py migrate
```
3. Recharge l'application web dans l'onglet "Web"
4. Accède à : https://founatek224.pythonanywhere.com/oscilloscope/

---

## 8. Connecter un ESP32 physique

### Code ESP32 à uploader (voir esp32_oscilloscope.ino)

Variables à modifier dans le code Arduino :
```cpp
const char* WIFI_SSID    = "TON_WIFI";
const char* WIFI_PASSWORD = "TON_MOT_DE_PASSE";
const char* API_TOKEN    = "Token TON_TOKEN_FOUNATEK";
const int   SESSION_ID   = 1;  // ID de ta session oscilloscope
```

Endpoint utilisé :
```
POST https://founatek224.pythonanywhere.com/oscilloscope/api/ingest/
```

---

## 9. Utiliser le bridge Arduino (port Série)

```bash
pip install pyserial requests
python serial_bridge.py --port COM3 --session 1 --token "Token TON_TOKEN"
```

Sur Linux/Mac : remplacer COM3 par /dev/ttyUSB0

---

## Structure des fichiers

```
oscilloscope/
├── __init__.py
├── apps.py
├── models.py          ← 6 modèles Django
├── serializers.py     ← Calculs métriques + FFT
├── views.py           ← API REST + vues HTML
├── urls.py            ← 15 routes
├── admin.py
├── migrations/
│   └── __init__.py
└── templates/
    └── oscilloscope/
        ├── oscilloscope.html   ← Interface principale
        ├── home.html           ← Liste des sessions
        └── create_session.html ← Nouvelle session
```

---

## Fonctionnalités disponibles

✅ Oscilloscope 2 canaux (CH1 + CH2)
✅ 8 types de signaux : sinusoïdal, carré, triangle, dent de scie, PWM, amorti, AM, bruit
✅ Contrôles : Volt/div, Temps/div, Offset, Trigger, Couplage DC/AC/GND
✅ Mesures automatiques : Vmax, Vmin, Vpp, Vrms, Vmoy, Fréquence, Période, Duty, Tr
✅ Analyse FFT en temps réel
✅ Sauvegarde de snapshots
✅ Analyse de composants : R, C, L, Diode, Filtres RC
✅ Export CSV
✅ Curseur de mesure interactif
✅ Réception données ESP32 via WiFi
✅ Bridge Arduino via port Série
✅ Compatible Founatek Token Auth
