# ============================================================
#  FOUNATEK NEXUS — Chatbot IA Complet
#  Fichier : espcontrol/chatbot_model.py
# ============================================================

import os
import random
import re
import logging
import requests
from django.contrib.admin.models import LogEntry, ADDITION, CHANGE, DELETION
from django.utils.timezone import localtime, now
from datetime import timedelta

from .utils import normalize, fuzzy_in, extract_rgb
from .models import (
    Relais, LED, DHTData, SoilData, SensorData, LEDColor,
    UploadedImage, Video, Comptage, NtcSensorData,
    Comment, Door, Badge, AccessRule, AccessLog,
    Device, AppareilData, AgentAlert, ActionLog,
    SensorRule, ChatMemory,
)

logger = logging.getLogger(__name__)

# ============================================================
#  GROQ API
# ============================================================
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL   = "llama-3.3-70b-versatile"

def call_groq(system_prompt, user_message, max_tokens=200):
    try:
        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        }
        body = {
            "model": GROQ_MODEL,
            "max_tokens": max_tokens,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_message}
            ]
        }
        resp = requests.post(GROQ_API_URL, headers=headers, json=body, timeout=8)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        logger.error(f"Erreur Groq API : {e}")
        return ""


# ============================================================
#  CHATBOT FOUNATEK NEXUS
# ============================================================
class Chatbot:

    RELAIS_MAPPING = {
        "salon": 1, "chambre": 2, "garage": 3,
        "relais1": 1, "relais 1": 1, "relay1": 1,
        "relais2": 2, "relais 2": 2, "relay2": 2,
        "relais3": 3, "relais 3": 3, "relay3": 3,
    }

    AQI = {
        "pm2p5":     {"bon": 15,  "modere": 35,  "mauvais": 55},
        "pm10":      {"bon": 45,  "modere": 75,  "mauvais": 150},
        "mq135_ppm": {"bon": 200, "modere": 400, "mauvais": 700},
    }

    INTENT_WORDS = {
        "on": {
            "allume", "allumer", "allumee",
            "active", "activer",
            "mets", "mettre", "met",
            "turn on", "switch on", "enable",
            "ouvre", "ouvrir", "start", "demarrer"
        },
        "off": {
            "eteins", "eteindre", "eteint",
            "coupe", "couper",
            "desactive", "desactiver",
            "turn off", "switch off", "disable",
            "stop", "arrete", "ferme"
        },
        "toggle": {
            "bascule", "basculer", "inverse",
            "inverser", "switch", "change", "changer"
        },
        "etat": {
            "etat", "status", "statut",
            "verifie", "montre"
        },
        "air_quality": {
            "pm2.5", "pm25", "pm2p5", "pm10",
            "particules", "particule", "poussiere",
            "pollution", "aqi", "indice",
            "air", "pm", "qualite", "mesure",
            "donnees", "capteur", "capteurs",
            "sds011", "sds", "conakry",
            "atmosphere", "environnement",
            "nexus", "station", "lecture"
        },
        "gaz": {
            "gaz", "mq135", "mq", "co2", "co",
            "no2", "ppm", "concentration", "toxique",
            "fumee", "odeur", "polluant", "chimique",
            "benzene", "ammoniac", "nh3"
        },
        "temperature": {
            "temperature", "temp", "thermometre",
            "chaud", "froid", "chaleur", "dht", "dht11",
            "degre", "celsius", "therm", "tiede",
            "brulant", "glacial", "canicule"
        },
        "humidite": {
            "humidite", "hum", "humid",
            "hygrometre", "sec", "seche",
            "vapeur", "moite", "moiteur", "humide"
        },
        "gps": {
            "gps", "position", "localisation", "location",
            "coordonnees", "latitude", "longitude",
            "satellite", "carte", "map", "where",
            "l76x", "gnss"
        },
        "device": {
            "appareil", "device", "esp32",
            "capteur_pm_001", "connecte", "online",
            "materiel", "hardware"
        },
        "alerte": {
            "alerte", "alertes", "alert", "urgence",
            "danger", "critique", "warning", "anomalie",
            "anomalies", "probleme", "erreur", "issue",
            "notification", "notif", "alarme"
        },
        "stats": {
            "statistique", "statistiques", "stats",
            "moyenne", "min", "max", "bilan", "rapport",
            "analyse", "evolution", "tendance",
            "24h", "journee", "semaine"
        },
        "regles": {
            "regle", "regles", "rule", "rules",
            "seuil", "seuils", "limite", "limites",
            "automatique", "auto", "declencheur"
        },
        "rgb": {
            "rgb", "couleur", "color", "ws2812",
            "neopixel", "ambiance", "leds", "bande"
        },
        "led_simple": {
            "led", "lumiere", "ampoule", "lampe", "eclairage"
        },
        "acces": {
            "acces", "porte", "portes",
            "badge", "badges", "rfid", "entree",
            "securite", "verrou", "cle"
        },
        "media": {
            "image", "images", "photo", "photos",
            "video", "camera", "surveillance", "capture"
        },
        "comptage": {
            "compte", "comptage", "compteur",
            "combien", "nombre", "total", "compter"
        },
        "historique": {
            "historique", "history", "journal",
            "log", "logs", "actions", "recent",
            "passe", "precedent", "dernier"
        },
        "bio": {
            "qui est elhadj", "elhadj diallo",
            "who is elhadj", "createur", "auteur",
            "developpeur", "etudiant", "stagiaire"
        },
        "founatek": {
            "founatek", "founa", "founatek iot",
            "platform iot", "projet", "iq pro",
            "air conakry", "odc"
        },
        "help": {
            "aide", "help", "assistance", "commandes",
            "que peux tu faire", "menu", "options", "tuto"
        },
    }

    ALIAS_PM     = {"air", "pm", "qualite", "mesure", "donnees",
                    "capteur", "capteurs", "sds", "nexus", "station",
                    "pollution", "poussiere", "particule", "conakry",
                    "atmosphere", "environnement", "lecture", "indice"}
    ALIAS_GAZ    = {"gaz", "mq", "co2", "ppm", "toxique",
                    "fumee", "odeur", "polluant", "chimique"}
    ALIAS_TEMP   = {"temp", "chaud", "froid", "chaleur", "dht",
                    "degre", "celsius", "therm", "tiede", "brulant"}
    ALIAS_HUM    = {"humide", "humid", "hum", "sec", "seche",
                    "vapeur", "moite", "moiteur"}
    ALIAS_RESUME = {"tout", "resume", "situation", "bilan",
                    "general", "complet", "global", "synthese", "overview"}
    ALIAS_ALERTE = {"alerte", "alertes", "alert", "urgence",
                    "danger", "critique", "warning", "anomalie",
                    "probleme", "erreur", "alarme", "notif"}
    ALIAS_GPS    = {"gps", "position", "localisation", "latitude",
                    "longitude", "satellite", "carte", "gnss"}
    ALIAS_STATS  = {"stats", "statistiques", "moyenne", "bilan",
                    "rapport", "analyse", "evolution", "24h"}
    ALIAS_DEVICE = {"appareil", "device", "esp32", "hardware",
                    "materiel", "connecte", "online"}

    REPONSES_ON = [
        "✅ {nom} est maintenant ACTIVÉ.",
        "💡 Activation de {nom} confirmée.",
        "⚡ C'est fait — {nom} est allumé."
    ]
    REPONSES_OFF = [
        "🛑 {nom} est maintenant ÉTEINT.",
        "💤 {nom} désactivé avec succès.",
        "🌙 C'est fait — {nom} est éteint."
    ]
    REPONSES_ALLUME_FR = REPONSES_ON
    REPONSES_ETEINS_FR = REPONSES_OFF

    BIO_TEXT = (
        "👤 Elhadj Abdourahmane Diallo — Étudiant L3 Physique Appliquée, "
        "Université de Lille (FST). Stagiaire ODC Orange Guinée, Conakry.\n"
        "🚀 Projet : FOUNATEK NEXUS AIR CONAKRY IQ PRO\n"
        "🔗 Portfolio : https://elhadj23diallo.github.io/site_elhad_portfolio/"
    )

    FOUNATEK_TEXT = (
        "🌍 FOUNATEK NEXUS AIR CONAKRY IQ PRO\n"
        "Station IoT de mesure de qualité de l'air — ODC Orange Guinée, Conakry\n"
        "📡 Capteurs : SDS011 (PM2.5/PM10), MQ-135 (Gaz), DHT11 (T°/Hum), GPS L76X\n"
        "🧠 Agent IA : Détection anomalies Z-Score, alertes automatiques\n"
        "🌐 founatek224.pythonanywhere.com/air-quality/"
    )

    SYSTEM_PROMPT_GROQ = """Tu es l'assistant IA de FOUNATEK NEXUS, station IoT de qualité de l'air à Conakry.
Traduis les demandes en commandes courtes parmi :
pm25, pm10, gaz, temperature, humidite, gps, device, alertes, stats, regles, historique,
allume relais N, eteins relais N, etat relais N (N=1,2,3), aide, founatek, bio

Réponds UNIQUEMENT avec la commande. Pas de phrase. Si plusieurs, sépare par virgule.
Si tu ne sais pas : inconnu

Exemples :
"C'est quoi la pollution ?" -> "pm25, pm10"
"Il fait chaud ?" -> "temperature"
"Alertes récentes ?" -> "alertes"
"Allume le premier relais" -> "allume relais 1"
"Tout va bien ?" -> "pm25, pm10, gaz, temperature, alertes"
"air" -> "pm25, pm10"
"gaz" -> "gaz"
"temp" -> "temperature"
"Parle moi de la pollution à Conakry" -> "pm25, pm10"
"""

    # ============================================================
    def __init__(self, user):
        self.user = user
        self._memory = None

    # ── MÉMOIRE ──────────────────────────────────────────────
    @property
    def memory(self):
        if self._memory is None:
            self._memory, _ = ChatMemory.objects.get_or_create(user=self.user)
        return self._memory

    def save_memory(self, device=None, sensor=None, action=None, message=None):
        m = self.memory
        if device:  m.last_device = device
        if sensor:  m.last_sensor = sensor
        if action:  m.last_action = action
        if message: m.last_message = message
        m.save()

    def get_relais_map(self):
        rmap = dict(self.RELAIS_MAPPING)
        for r in Relais.objects.filter(user=self.user):
            nom = normalize(r.nom)
            rmap[nom] = r.num
            rmap[f"relais{r.num}"] = r.num
            rmap[f"relais {r.num}"] = r.num
        return rmap

    # ============================================================
    #  DONNÉES IoT — CORRIGÉ : order_by('-last_seen')
    # ============================================================

    def get_latest_data(self):
        # ── CORRECTION : prend le device vu le plus récemment ──
        device = Device.objects.filter(
            user=self.user,
            is_active=True
        ).order_by('-last_seen').first()

        # Fallback — prend n'importe quel device actif
        if not device:
            device = Device.objects.filter(
                is_active=True
            ).order_by('-last_seen').first()

        if not device:
            return None, None

        latest = AppareilData.objects.filter(
            device=device
        ).order_by('-received_at').first()

        return device, latest

    def get_aqi_status(self, pm25):
        if pm25 is None: return "❓ Inconnu"
        t = self.AQI["pm2p5"]
        if pm25 <= t["bon"]:     return "✅ Bon"
        if pm25 <= t["modere"]:  return "⚠️ Modéré"
        if pm25 <= t["mauvais"]: return "🔴 Mauvais"
        return "☠️ Très mauvais"

    def get_stats_24h(self):
        depuis  = now() - timedelta(hours=24)
        devices = Device.objects.filter(user=self.user)
        readings = AppareilData.objects.filter(
            device__in=devices, received_at__gte=depuis
        )
        sensors = ['pm2p5', 'pm10', 'mq135_ppm', 'temperature', 'humidity']
        stats = {}
        for s in sensors:
            vals = [
                r.payload.get(s) for r in readings
                if r.payload and isinstance(r.payload.get(s), (int, float))
            ]
            if vals:
                stats[s] = {
                    "avg": round(sum(vals)/len(vals), 2),
                    "min": round(min(vals), 2),
                    "max": round(max(vals), 2),
                    "count": len(vals)
                }
        return stats

    # ============================================================
    #  HANDLERS
    # ============================================================

    def handle_pm(self):
        device, latest = self.get_latest_data()
        if not latest or not latest.payload:
            return "📡 Aucune donnée SDS011 — vérifiez que l'ESP32 envoie des données."
        p    = latest.payload
        pm25 = p.get('pm2p5')
        pm10 = p.get('pm10')
        ts   = localtime(latest.received_at).strftime('%H:%M:%S')
        status = self.get_aqi_status(pm25)
        self.save_memory(device=device, sensor='pm2p5')
        lines = [f"💨 Qualité de l'air — {device.name} ({ts})"]
        if pm25 is not None: lines.append(f"  🔵 PM2.5 : {pm25} µg/m³")
        if pm10 is not None: lines.append(f"  🟤 PM10  : {pm10} µg/m³")
        lines.append(f"  📊 AQI   : {status}")
        if pm25 and pm25 > self.AQI["pm2p5"]["mauvais"]:
            lines.append("  ⚠️ Évitez de sortir, portez un masque FFP2 !")
        return "\n".join(lines)

    def handle_gaz(self):
        device, latest = self.get_latest_data()
        if not latest or not latest.payload:
            return "🔬 Aucune donnée MQ-135 disponible."
        p   = latest.payload
        ppm = p.get('mq135_ppm')
        ts  = localtime(latest.received_at).strftime('%H:%M:%S')
        self.save_memory(device=device, sensor='mq135_ppm')
        if ppm is None:
            return "🔬 Donnée MQ-135 absente du dernier payload."
        t = self.AQI["mq135_ppm"]
        if ppm <= t["bon"]:       statut = "✅ Air sain"
        elif ppm <= t["modere"]:  statut = "⚠️ Concentration modérée"
        elif ppm <= t["mauvais"]: statut = "🔴 Élevée — Aérez !"
        else:                     statut = "☠️ DANGER — Quittez la zone !"
        return (
            f"🔬 MQ-135 Gaz — {device.name} ({ts})\n"
            f"  💨 Concentration : {ppm} PPM\n"
            f"  📊 Statut : {statut}"
        )

    def handle_temperature(self):
        device, latest = self.get_latest_data()
        if not latest or not latest.payload:
            return "🌡️ Aucune donnée DHT11 disponible."
        p  = latest.payload
        t  = p.get('temperature')
        h  = p.get('humidity')
        ts = localtime(latest.received_at).strftime('%H:%M:%S')
        self.save_memory(device=device, sensor='temperature')
        lines = [f"🌡️ DHT11 — {device.name} ({ts})"]
        if t is not None:
            icon = "🔥" if t > 35 else ("❄️" if t < 18 else "🌤️")
            lines.append(f"  {icon} Température : {t}°C")
        if h is not None:
            icon = "💧" if h > 70 else ("🏜️" if h < 30 else "✅")
            lines.append(f"  {icon} Humidité    : {h}%")
        return "\n".join(lines)

    def handle_gps(self):
        device, latest = self.get_latest_data()
        if not latest or not latest.payload:
            return "📡 Aucune donnée GPS disponible."
        p    = latest.payload
        lat  = p.get('latitude')
        lon  = p.get('longitude')
        sats = p.get('satellites')
        ts   = localtime(latest.received_at).strftime('%H:%M:%S')
        if not lat or not lon:
            return "📡 Signal GPS non acquis — vérifiez l'antenne L76X."
        lines = [
            f"📡 GPS L76X — {device.name} ({ts})",
            f"  📍 Latitude  : {lat}",
            f"  📍 Longitude : {lon}",
        ]
        if sats: lines.append(f"  🛰️ Satellites : {sats}")
        lines.append(f"  🗺️ Maps : https://maps.google.com/?q={lat},{lon}")
        return "\n".join(lines)

    def handle_device(self):
        devices = Device.objects.filter(user=self.user)
        if not devices.exists():
            return "📱 Aucun appareil enregistré."
        lines = [f"📱 Vos appareils ({devices.count()}) :"]
        for d in devices:
            last  = localtime(d.last_seen).strftime('%d/%m %H:%M') if d.last_seen else "Jamais"
            count = AppareilData.objects.filter(device=d).count()
            etat  = "🟢 En ligne" if d.is_active else "🔴 Hors ligne"
            lines.append(
                f"\n  🔌 {d.name} ({d.device_id})\n"
                f"     {etat} | Vu : {last} | {count} mesures"
            )
        return "\n".join(lines)

    def handle_alertes(self):
        alerts = AgentAlert.objects.filter(
            user=self.user, is_read=False
        ).order_by('-created_at')[:10]
        if not alerts.exists():
            return "✅ Aucune alerte active — tout semble normal !"
        lines = [f"🚨 {alerts.count()} alerte(s) non lue(s) :"]
        for a in alerts:
            ts   = localtime(a.created_at).strftime('%H:%M')
            icon = {"INFO": "ℹ️", "WARN": "⚠️", "CRITICAL": "🔴"}.get(a.level, "❓")
            lines.append(f"  {icon} [{ts}] {a.message}")
        return "\n".join(lines)

    def handle_stats(self):
        stats = self.get_stats_24h()
        if not stats:
            return "📊 Pas assez de données pour les statistiques."
        labels = {
            'pm2p5':      ('🔵', 'PM2.5',      'µg/m³'),
            'pm10':       ('🟤', 'PM10',       'µg/m³'),
            'mq135_ppm':  ('🔬', 'Gaz MQ-135', 'PPM'),
            'temperature':('🌡️', 'Température','°C'),
            'humidity':   ('💧', 'Humidité',   '%'),
        }
        lines = ["📊 Statistiques 24h — FOUNATEK NEXUS :"]
        for key, (icon, label, unit) in labels.items():
            if key in stats:
                s = stats[key]
                lines.append(
                    f"  {icon} {label} : moy={s['avg']}{unit} "
                    f"| min={s['min']} | max={s['max']} "
                    f"| {s['count']} mesures"
                )
        return "\n".join(lines)

    def handle_regles(self):
        rules = SensorRule.objects.filter(user=self.user, active=True)
        if not rules.exists():
            return "📋 Aucune règle automatique configurée."
        lines = [f"📋 {rules.count()} règle(s) active(s) :"]
        for r in rules:
            seuil = f"max={r.max_value}" if r.max_value else f"min={r.min_value}"
            lines.append(
                f"  ⚙️ [{r.code}] {r.sensor} {seuil} "
                f"→ {r.action_type} Relais {r.target_num} [{r.level}]"
            )
        return "\n".join(lines)

    def handle_historique(self):
        actions = ActionLog.objects.filter(
            user=self.user
        ).order_by('-created_at')[:10]
        if not actions.exists():
            return "📋 Aucune action récente."
        lines = ["🕒 Historique :"]
        for a in actions:
            ts = localtime(a.created_at).strftime('%d/%m %H:%M')
            lines.append(f"  {ts} — {a.action}")
        return "\n".join(lines)

    def handle_resume(self):
        device, latest = self.get_latest_data()
        if not latest or not latest.payload:
            return "📡 Aucune donnée — l'ESP32 est-il connecté ?"
        p    = latest.payload
        ts   = localtime(latest.received_at).strftime('%d/%m %H:%M:%S')
        pm25 = p.get('pm2p5', 'N/A')
        pm10 = p.get('pm10', 'N/A')
        gaz  = p.get('mq135_ppm', 'N/A')
        temp = p.get('temperature', 'N/A')
        hum  = p.get('humidity', 'N/A')
        lat  = p.get('latitude', 'N/A')
        lon  = p.get('longitude', 'N/A')
        status   = self.get_aqi_status(pm25 if isinstance(pm25, (int, float)) else None)
        n_alerts = AgentAlert.objects.filter(user=self.user, is_read=False).count()
        return "\n".join([
            f"🌍 FOUNATEK NEXUS — Résumé ({ts})",
            f"  📡 Station  : {device.name}",
            f"  🔵 PM2.5    : {pm25} µg/m³",
            f"  🟤 PM10     : {pm10} µg/m³",
            f"  🔬 MQ-135   : {gaz} PPM",
            f"  🌡️ Temp     : {temp}°C | 💧 Hum : {hum}%",
            f"  📊 AQI      : {status}",
            f"  📍 GPS      : {lat}, {lon}",
            f"  🚨 Alertes  : {n_alerts} non lue(s)",
        ])

    def handle_relais(self, num, action):
        try:
            relais = Relais.objects.get(user=self.user, num=num)
        except Relais.DoesNotExist:
            return f"⚠️ Relais {num} introuvable. Créez-le dans le dashboard."
        nom = relais.nom or f"Relais {num}"
        if action == "allume":
            relais.etat = True; relais.save()
            return random.choice(self.REPONSES_ON).format(nom=nom)
        elif action == "eteins":
            relais.etat = False; relais.save()
            return random.choice(self.REPONSES_OFF).format(nom=nom)
        elif action == "toggle":
            relais.etat = not relais.etat; relais.save()
            etat = "allumé" if relais.etat else "éteint"
            return f"↔️ {nom} basculé — maintenant {etat}."
        else:
            etat = "allumé 💡" if relais.etat else "éteint 🌙"
            return f"ℹ️ {nom} (Relais {num}) : {etat}"

    def handle_acces(self, target="general"):
        if target == "porte":
            logs = AccessLog.objects.filter(user=self.user).order_by('-timestamp')[:5]
            if not logs.exists():
                return "🚪 Aucun historique d'accès récent."
            lines = ["🚪 Derniers accès :"]
            for log in logs:
                s = "✅ Autorisé" if log.allowed else "❌ Refusé"
                d = log.door.name if log.door else "?"
                b = (log.badge.label if log.badge and log.badge.label else log.uid or "Inconnu")
                lines.append(f"  {localtime(log.timestamp).strftime('%d/%m %H:%M')} : {d} par {b} ({s})")
            return "\n".join(lines)
        elif target == "badge":
            badges = Badge.objects.filter(owner=self.user)
            if not badges.exists():
                return "🆔 Aucun badge associé."
            lines = [f"🆔 {badges.count()} badge(s) :"]
            for b in badges:
                lines.append(f"  - {b.label or b.uid} ({'Actif ✅' if b.is_active else 'Inactif ❌'})")
            return "\n".join(lines)
        else:
            logs = AccessLog.objects.filter(user=self.user).order_by('-timestamp')[:3]
            if not logs.exists():
                return "🛡️ Aucun événement récent."
            lines = ["🛡️ Derniers événements :"]
            for log in logs:
                s = "✅" if log.allowed else "❌"
                lines.append(f"  {s} {localtime(log.timestamp).strftime('%H:%M')} — {log.uid}")
            return "\n".join(lines)

    # ============================================================
    #  PARSING DES INTENTIONS
    # ============================================================

    def parse_intent(self, msg):
        msg_norm = normalize(msg)
        tokens   = set(msg_norm.lower().split())
        intents  = []

        # ── ÉTAPE 1 : Alias courts prioritaires ──────────────
        if tokens & self.ALIAS_RESUME:
            return [{"type": "resume"}]

        if tokens & self.ALIAS_PM:
            intents.append({"type": "pm"})

        if tokens & self.ALIAS_GAZ:
            intents.append({"type": "gaz"})

        if tokens & self.ALIAS_TEMP:
            intents.append({"type": "temperature"})

        if (tokens & self.ALIAS_HUM) and not (tokens & self.ALIAS_TEMP):
            intents.append({"type": "humidite"})

        if tokens & self.ALIAS_ALERTE:
            intents.append({"type": "alertes"})

        if tokens & self.ALIAS_GPS:
            intents.append({"type": "gps"})

        if tokens & self.ALIAS_STATS:
            intents.append({"type": "stats"})

        if tokens & self.ALIAS_DEVICE:
            intents.append({"type": "device"})

        # ── ÉTAPE 2 : INTENT_WORDS complets ──────────────────
        if tokens & self.INTENT_WORDS["air_quality"] and \
           not any(i["type"] == "pm" for i in intents):
            intents.append({"type": "pm"})

        if tokens & self.INTENT_WORDS["gaz"] and \
           not any(i["type"] == "gaz" for i in intents):
            intents.append({"type": "gaz"})

        if tokens & self.INTENT_WORDS["temperature"] and \
           not any(i["type"] == "temperature" for i in intents):
            intents.append({"type": "temperature"})

        if (tokens & self.INTENT_WORDS["humidite"]) and \
           not (tokens & self.INTENT_WORDS["temperature"]) and \
           not any(i["type"] == "humidite" for i in intents):
            intents.append({"type": "humidite"})

        if tokens & self.INTENT_WORDS["gps"] and \
           not any(i["type"] == "gps" for i in intents):
            intents.append({"type": "gps"})

        if tokens & self.INTENT_WORDS["device"] and \
           not any(i["type"] == "device" for i in intents):
            intents.append({"type": "device"})

        if tokens & self.INTENT_WORDS["alerte"] and \
           not any(i["type"] == "alertes" for i in intents):
            intents.append({"type": "alertes"})

        if tokens & self.INTENT_WORDS["stats"] and \
           not any(i["type"] == "stats" for i in intents):
            intents.append({"type": "stats"})

        if tokens & self.INTENT_WORDS["regles"]:
            intents.append({"type": "regles"})

        if tokens & self.INTENT_WORDS["historique"] and \
           not any(i["type"] == "stats" for i in intents):
            intents.append({"type": "historique"})

        if tokens & self.INTENT_WORDS["acces"]:
            target = "general"
            if "porte" in tokens or "portes" in tokens: target = "porte"
            elif "badge" in tokens or "badges" in tokens: target = "badge"
            intents.append({"type": "acces", "target": target})

        if tokens & self.INTENT_WORDS["media"]:
            target = "video" if "video" in tokens else "image"
            intents.append({"type": "media", "target": target})

        if tokens & self.INTENT_WORDS["comptage"]:
            intents.append({"type": "comptage"})

        if tokens & self.INTENT_WORDS["rgb"]:
            action = "eteins" if (tokens & self.INTENT_WORDS["off"]) else "set"
            intents.append({"type": "rgb", "action": action, "raw": msg})

        if (tokens & self.INTENT_WORDS["led_simple"]) and \
           not (tokens & self.INTENT_WORDS["rgb"]):
            action = None
            if tokens & self.INTENT_WORDS["on"]:    action = "allume"
            elif tokens & self.INTENT_WORDS["off"]: action = "eteins"
            if action:
                intents.append({"type": "led", "action": action})

        # ── ÉTAPE 3 : Relais ─────────────────────────────────
        rmap = self.get_relais_map()
        relais_num = None

        match = re.search(r'\b([1-9])\b', msg_norm)
        if match:
            relais_num = int(match.group(1))

        if not relais_num:
            for nom, num in rmap.items():
                if nom in msg_norm:
                    relais_num = num
                    break

        if relais_num and 1 <= relais_num <= 10:
            action = None
            if tokens & self.INTENT_WORDS["on"]:       action = "allume"
            elif tokens & self.INTENT_WORDS["off"]:    action = "eteins"
            elif tokens & self.INTENT_WORDS["toggle"]: action = "toggle"
            elif tokens & self.INTENT_WORDS["etat"]:   action = "etat"
            if action:
                intents.append({"type": "relais", "num": relais_num, "action": action})

        if not any(i.get("type") == "relais" for i in intents):
            for nom, num in self.RELAIS_MAPPING.items():
                if fuzzy_in(nom, tokens):
                    action = None
                    if tokens & self.INTENT_WORDS["on"]:    action = "allume"
                    elif tokens & self.INTENT_WORDS["off"]: action = "eteins"
                    elif tokens & self.INTENT_WORDS["toggle"]: action = "toggle"
                    elif tokens & self.INTENT_WORDS["etat"]:   action = "etat"
                    if action:
                        intents.append({"type": "relais", "num": num, "action": action})
                    break

        return intents

    # ============================================================
    #  EXÉCUTION
    # ============================================================

    def execute_intent(self, intent):
        t = intent.get("type")

        if t == "resume":      return self.handle_resume()
        if t == "pm":          return self.handle_pm()
        if t == "gaz":         return self.handle_gaz()
        if t == "temperature": return self.handle_temperature()
        if t == "humidite":    return self.handle_temperature()
        if t == "gps":         return self.handle_gps()
        if t == "device":      return self.handle_device()
        if t == "alertes":     return self.handle_alertes()
        if t == "stats":       return self.handle_stats()
        if t == "regles":      return self.handle_regles()
        if t == "historique":  return self.handle_historique()
        if t == "acces":       return self.handle_acces(intent.get("target", "general"))

        if t == "media":
            if intent.get("target") == "video":
                vid = Video.objects.filter(user=self.user).last()
                return f"📹 Dernière vidéo : {vid.video.name if vid else 'Aucune'}"
            img = UploadedImage.objects.filter(user=self.user).order_by('-created_at').first()
            return f"🖼️ Dernière image : {img.image.name if img else 'Aucune'}"

        if t == "comptage":
            c = Comptage.objects.filter(user=self.user).last()
            return (f"🔢 Dernier comptage : {c.compteur} "
                    f"({localtime(c.timestamp).strftime('%d/%m %H:%M')})"
                    if c else "🔢 Aucun comptage enregistré.")

        if t == "rgb":
            if intent.get("action") == "eteins":
                LEDColor.objects.create(user=self.user, r=0, g=0, b=0)
                return "⚫ LED RGB éteinte."
            rgb = extract_rgb(intent.get("raw", ""))
            if rgb and rgb != (0, 0, 0):
                LEDColor.objects.create(user=self.user, r=rgb[0], g=rgb[1], b=rgb[2])
                return f"🎨 Couleur RGB appliquée : {rgb}"
            return "⚠️ Couleur non reconnue. Exemple : 'mets du rouge'."

        if t == "led":
            led, _ = LED.objects.get_or_create(user=self.user)
            if intent.get("action") == "allume":
                led.etat = True; led.save()
                return "💡 LED allumée."
            led.etat = False; led.save()
            return "🌙 LED éteinte."

        if t == "relais":
            return self.handle_relais(intent.get("num", 1), intent.get("action", "etat"))

        return "🤔 Commande non reconnue."

    # ============================================================
    #  POINT D'ENTRÉE PRINCIPAL
    # ============================================================

    def get_response(self, raw_msg):
        msg = normalize(raw_msg)

        # Arrêt d'urgence
        if msg in {"stop", "urgence", "emergency"}:
            Relais.objects.filter(user=self.user).update(etat=False)
            return "🛑 ARRÊT D'URGENCE — Tous les relais éteints !"

        # Bio
        if any(m in msg for m in self.INTENT_WORDS["bio"]):
            return self.BIO_TEXT

        # Founatek
        if any(m in msg for m in self.INTENT_WORDS["founatek"]):
            return self.FOUNATEK_TEXT

        # Aide
        if any(m in msg for m in self.INTENT_WORDS["help"]):
            return {
                "reponse": "🤖 Assistant FOUNATEK NEXUS — Que voulez-vous savoir ?",
                "buttons": [
                    {"text": "💨 Qualité de l'air", "value": "air"},
                    {"text": "🌡️ Température",      "value": "temperature"},
                    {"text": "🔬 Gaz MQ-135",       "value": "gaz"},
                    {"text": "📡 GPS",               "value": "gps"},
                    {"text": "🚨 Alertes",           "value": "alertes"},
                    {"text": "📊 Statistiques",      "value": "stats"},
                    {"text": "📱 Appareil",          "value": "appareil"},
                    {"text": "🌍 Résumé complet",    "value": "tout"},
                    {"text": "⚡ Relais 1",          "value": "etat relais 1"},
                    {"text": "⚡ Relais 2",          "value": "etat relais 2"},
                    {"text": "⚡ Relais 3",          "value": "etat relais 3"},
                ]
            }

        # Parsing local
        intents = self.parse_intent(raw_msg)

        # Fallback Groq
        if not intents:
            translated = call_groq(self.SYSTEM_PROMPT_GROQ, raw_msg)
            if translated and translated not in ("inconnu", ""):
                logger.info(f"Groq: '{raw_msg}' -> '{translated}'")
                intents = self.parse_intent(translated)

        # Exécution
        if not intents:
            return (
                "🤔 Je n'ai pas compris. Essayez :\n"
                "  • 'air' ou 'pm25'\n"
                "  • 'alertes'\n"
                "  • 'temperature'\n"
                "  • 'tout' pour un résumé complet\n"
                "Tapez 'aide' pour voir toutes les commandes."
            )

        responses  = []
        seen_types = set()
        for intent in intents:
            key = (intent.get("type"), intent.get("num"), intent.get("action"))
            if key not in seen_types:
                result = self.execute_intent(intent)
                if result:
                    responses.append(result)
                seen_types.add(key)

        return "\n\n".join(responses) if responses else "..."