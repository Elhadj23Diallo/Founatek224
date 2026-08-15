import random
import re
import logging
import json
from django.contrib.admin.models import LogEntry, ADDITION, CHANGE, DELETION
from django.utils.timezone import localtime
# Assurez-vous que les imports relatifs fonctionnent dans votre structure
from .utils import normalize, fuzzy_in, extract_rgb
# On importe les modèles nécessaires
from .models import (
    Relais, LED, DHTData, SoilData, SensorData, LEDColor,
    UploadedImage, Video, Comptage, NtcSensorData,
    Comment, Door, Badge, AccessRule, AccessLog
)
import google.generativeai as genai

logger = logging.getLogger(__name__)

# === Config Gemini Pro ===
# ⚠️ ATTENTION : CLÉ API EN CLAIR.
GEMINI_API_KEY = "AIzaSyCNNinYlYn2dJPOgv5s79MYufVC0yw8sY8"
try:
    genai.configure(api_key=GEMINI_API_KEY)
except Exception as e:
    logger.error(f"Erreur configuration Gemini: {e}")

class Chatbot:
    RELAIS_MAPPING = {"salon": 1, "chambre": 2, "garage": 3}

    # --- MOTS-CLÉS ---
    INTENT_WORDS = {
        "on": {
            "allume", "allumer", "allumé", "allumée",
            "active", "activer", "activé",
            "mets", "mettre", "met",
            "turn on", "switch on", "enable",
            "clair", "lumiere", "jour"
        },
        "off": {
            "eteins", "éteins", "eteindre", "éteindre", "eteint", "éteint", "éteinte",
            "coupe", "couper", "coupé",
            "desactive", "désactive", "desactiver", "désactiver", "desactivé", "désactivé",
            "turn off", "switch off", "disable",
            "sombre", "noir", "nuit", "stop", "arrete", "arrête"
        },
        "toggle": {
            "bascule", "basculer", "inverse", "inverser", "switch", "change", "changer"
        },
        "etat": {
            "etat", "état", "status", "statut", "state",
            "comment est", "est ce que", "vérifie", "verifie"
        },
        "capteurs": {"capteur", "capteurs", "temperature", "température", "humidite", "humidité", "co2", "gaz", "air", "sol", "dht", "sensor", "sensors", "données", "climat", "meteo", "météo"},
        "rgb": {"rgb", "couleur", "color", "ws2812", "neopixel", "ambiance", "leds"},
        "led_simple": {"led", "lumière simple", "ampoule"},
        "acces": {"accès", "acces", "porte", "portes", "badge", "badges", "entrée", "sorties", "qui est entré", "historique accès", "passages"},
        "media": {"image", "images", "photo", "photos", "vidéo", "video", "caméra", "camera"},
        "comptage": {"compte", "comptage", "compteur", "combien", "nombre"},
        "bio": {"qui est elhadj", "cest qui elhadj", "elhadj diallo", "who is elhadj", "le créateur", "auteur"},
        "founatek": {"founatek", "founa", "founatek iot", "platform iot", "iot application", "le projet", "c'est quoi"},
        "help": {"aide", "help", "assistance", "commandes", "que peux tu faire", "menu", "options"},
        "historique": {"actions", "historique", "journal", "mes actions", "actions récentes", "history", "recent actions", "log", "logs"}
    }

    # --- RÉPONSES UNIFORMISÉES ---
    REPONSES_ALLUME_FR = [
        "✅ {piece} est maintenant ALLUMÉE.",
        "💡 Activation de {piece} confirmée.",
        "✨ C'est fait, {piece} est allumée."
    ]
    REPONSES_ETEINS_FR = [
        "🛑 {piece} est maintenant ÉTEINTE.",
        "💤 Désactivation de {piece} confirmée.",
        "🌙 C'est fait, {piece} est éteinte."
    ]
    REPONSES_TOGGLE_FR = [
        "↔️ {piece} a basculé : elle est maintenant {nouvel_etat}.",
        "✅ Changement d'état : {piece} est {nouvel_etat}."
    ]
    REPONSES_ETAT_FR = [
        "ℹ️ L'état actuel de {piece} est : {etat}.",
        "📟 Statut {piece} : {etat}."
    ]

    BIO_TEXT = ("👤 Elhadj Abdourahmane Diallo est étudiant en Licence 3 Physique Appliquée... (Portfolio: https://elhadj23diallo.github.io/site_elhad_portfolio/)")
    FOUNATEK_TEXT = "🌍 Founatek IoT est une plateforme de gestion et de contrôle d'appareils connectés..."

    HELP_TOPICS = {
        "1": "Actions Relais (Allumer/Éteindre salon...)",
        "2": "Capteurs (Température, Humidité...)",
        "3": "Lumière RGB (Couleurs et extinction)",
        "4": "Accès & Sécurité (Portes, Badges)",
        "5": "Médias & Comptage",
        "6": "À propos (Founatek/Elhadj)",
        "7": "Historique & API"
    }

    HELP_RESPONSES = {
        "1": "💡 Exemple : 'allume le salon', 'désactive le garage'.",
        "2": "📟 Exemple : 'quelle est la température ?'.",
        "3": "🎨 Exemple : 'mets du bleu', 'éteins la lumière rgb'.",
        "4": "🚪 Exemple : 'qui a ouvert la porte ?', 'historique des accès', 'liste des badges'.",
        "5": "🖼️ Exemple : 'montre les images' ou 'donne le comptage'.",
        "6": f"{FOUNATEK_TEXT}\n\n{BIO_TEXT}",
        "7": "🕒 Tape 'mes actions' pour l'historique. Tes clés API sont sur le dashboard."
    }

    # === PROMPT SYSTÈME (Cerveau de l'IA) ===
    SYSTEM_INSTRUCTION_GEMINI = """
Tu es le cerveau d'un système domotique intelligent.
Ton rôle est TRADUIRE les demandes utilisateurs en commandes standardisées.
Le système qui lira ta réponse ne comprend que des mots-clés précis.

Voici tes outils :
- Actions basiques : 'allume', 'éteins', 'bascule', 'etat'
- Appareils : 'salon', 'chambre', 'garage' (relais), 'led' (simple), 'rgb' (couleur)
- Capteurs : 'capteurs' (temp, hum, co2, etc.)
- Sécurité/Accès : 'accès' (pour historique général), 'porte' (état/historique porte), 'badge' (liste/état badges)
- Divers : 'image', 'vidéo', 'compteur'

Ta mission : Reformule la demande utilisateur en utilisant UNIQUEMENT ces mots-clés pour que l'action soit claire.
Si la demande contient plusieurs actions, sépare-les par des virgules.
Sois concis. Pas de phrase de politesse.

Exemples :
- "Il fait sombre salon" -> "allume salon"
- "Coupe la lumière dans le garage" -> "éteins garage"
- "Désactive la lumière d'ambiance" -> "éteins rgb"
- "Quelle est la température" -> "capteurs"
- "Qui a ouvert la porte ?" -> "accès, porte"
- "Montre moi les dernières photos" -> "image"
"""

    def __init__(self, user):
        self.user = user
        try:
            self.model = genai.GenerativeModel(
                "models/gemini-pro",
                system_instruction=self.SYSTEM_INSTRUCTION_GEMINI
            )
        except Exception as e:
             logger.error(f"Erreur init modèle Gemini: {e}")
             self.model = None

    # ... (get_user_history reste identique) ...
    def get_user_history(self, user=None, limit=100):
        user = user or self.user
        entries = LogEntry.objects.filter(user=user).order_by('-action_time')[:limit]
        history = []
        for e in entries:
            action_type = {ADDITION: "➕", CHANGE: "✏️", DELETION: "🗑️"}.get(e.action_flag, "❓")
            object_repr = e.object_repr[:30] + "..." if len(e.object_repr) > 30 else e.object_repr
            history.append(f"{localtime(e.action_time).strftime('%d/%m %H:%M')} {action_type} {object_repr}")
        return history if history else ["Aucune action enregistrée récemment."]

    # -------------------------
    # Parsing mis à jour (LOGIQUE ULTRA INTELLIGENTE : PAS DE DEVINETTE)
    # -------------------------
    def parse_actions(self, msg):
        msg = normalize(msg)
        actions = []
        parties = re.split(r"\s*(?:et|,|;|and|\n)\s*", msg)
        for p in parties:
            if not p.strip(): continue
            d = {"action": None, "piece": None, "type": None, "raw": p}
            tokens = set(p.lower().split())

            # --- NOUVEAUX TYPES ---
            if tokens & self.INTENT_WORDS["acces"]:
                d["type"] = "acces"
                if "porte" in tokens: d["target"] = "porte"
                elif "badge" in tokens: d["target"] = "badge"
                else: d["target"] = "general"
            elif tokens & self.INTENT_WORDS["media"]:
                 d["type"] = "media"
                 if "vidéo" in tokens or "video" in tokens: d["target"] = "video"
                 else: d["target"] = "image"
            elif tokens & self.INTENT_WORDS["comptage"]:
                 d["type"] = "comptage"
            # ----------------------

            elif tokens & self.INTENT_WORDS["rgb"]:
                d["type"] = "rgb"
                if any(t in self.INTENT_WORDS["off"] for t in tokens):
                    d["action"] = "eteins"
                else:
                    d["action"] = "set"

            elif tokens & self.INTENT_WORDS["led_simple"]:
                d["type"] = "led"
                if any(t in self.INTENT_WORDS["on"] for t in tokens): d["action"] = "allume"
                elif any(t in self.INTENT_WORDS["off"] for t in tokens): d["action"] = "eteins"
                # Pas de fallback sur "etat" ici. Si pas d'ordre clair, l'IA gérera.

            elif tokens & self.INTENT_WORDS["capteurs"]:
                d.update({"type": "capteur", "action": "get"})
            else:
                possibles = [t for t in tokens if fuzzy_in(t, self.RELAIS_MAPPING.keys())]
                if len(possibles) == 1:
                    piece = possibles[0]
                    # === LOGIQUE STRICTE ===
                    # On ne définit l'action que si un verbe est CLAIREMENT identifié.
                    # Sinon, on laisse 'action' à None, et l'IA prendra le relais.
                    if any(t in self.INTENT_WORDS["on"] for t in tokens):
                        d["action"] = "allume"
                    elif any(t in self.INTENT_WORDS["off"] for t in tokens):
                        d["action"] = "eteins"
                    elif any(t in self.INTENT_WORDS["toggle"] for t in tokens):
                        d["action"] = "toggle"
                    elif any(t in self.INTENT_WORDS["etat"] for t in tokens):
                        d["action"] = "etat"

                    # Si une action a été trouvée, on valide le type relais
                    if d["action"]:
                        d.update({"type": "relais", "piece": piece})

                elif len(possibles) > 1:
                    d.update({"type": "clarify", "options": possibles})

            if d["type"]:
                actions.append(d)
        return actions

    # -------------------------
    # Exécution des actions
    # -------------------------
    def execute_action(self, act):
        responses = []
        # Clarification
        if act["type"] == "clarify":
            options = ", ".join(act["options"])
            responses.append(f"🤔 Je ne suis pas sûr de quelle pièce vous parlez : {options} ?")

        # --- ACTIONS ACCÈS ---
        elif act["type"] == "acces":
            target = act.get("target")
            if target == "porte":
                 logs = AccessLog.objects.filter(user=self.user).order_by('-timestamp')[:5]
                 if logs:
                     res = ["🚪 Derniers accès aux portes :"]
                     for log in logs:
                         status = "✅ Autorisé" if log.allowed else "❌ Refusé"
                         door_name = log.door.name if log.door else "Porte inconnue"
                         badge_label = log.badge.label if log.badge and log.badge.label else (log.uid or "Inconnu")
                         res.append(f"- {localtime(log.timestamp).strftime('%d/%m %H:%M')} : {door_name} par {badge_label} ({status})")
                     responses.append("\n".join(res))
                 else:
                     responses.append("🚪 Aucun historique d'accès porte récent.")
            elif target == "badge":
                 badges = Badge.objects.filter(user=self.user)
                 if badges:
                      res = [f"🆔 Vos {badges.count()} badge(s) :"]
                      for b in badges:
                          status = "Actif" if b.is_active else "Inactif"
                          label = b.label or b.uid
                          res.append(f"- {label} ({status})")
                      responses.append("\n".join(res))
                 else:
                      responses.append("🆔 Aucun badge associé à votre compte.")
            else:
                 logs = AccessLog.objects.filter(user=self.user).order_by('-timestamp')[:3]
                 if logs:
                     res = ["🛡️ Derniers événements d'accès :"]
                     for log in logs:
                         status = "✅" if log.allowed else "❌"
                         res.append(f"- {localtime(log.timestamp).strftime('%H:%M')} : {log.uid} -> {log.door.name if log.door else '?'} ({status})")
                     responses.append("\n".join(res))
                 else:
                     responses.append("🛡️ Aucun événement d'accès récent.")

        # --- ACTIONS MÉDIA & COMPTAGE ---
        elif act["type"] == "media":
             if act.get("target") == "video":
                  vid = Video.objects.filter(user=self.user).last()
                  responses.append(f"📹 Dernière vidéo : {vid.video.name if vid else 'Aucune'}")
             else:
                  img = UploadedImage.objects.filter(user=self.user).last()
                  img_name = img.image.name if img and img.image else 'Aucune'
                  responses.append(f"🖼️ Dernière image : {img_name}")

        elif act["type"] == "comptage":
             compte = Comptage.objects.filter(user=self.user).last()
             if compte:
                  responses.append(f"🔢 Dernier comptage : {compte.valeur} (le {localtime(compte.timestamp).strftime('%d/%m à %H:%M')})")
             else:
                  responses.append("🔢 Aucun comptage enregistré.")
        # -------------------------

        # LED simple
        elif act["type"] == "led":
            led = LED.objects.filter(user=self.user).first()
            if led:
                piece_name = "la LED simple"
                if act["action"] == "allume":
                    led.etat = True
                    led.save()
                    responses.append(random.choice(self.REPONSES_ALLUME_FR).format(piece=piece_name))
                elif act["action"] == "eteins":
                    led.etat = False
                    led.save()
                    responses.append(random.choice(self.REPONSES_ETEINS_FR).format(piece=piece_name))
                else:
                    et = "allumée" if led.etat else "éteinte"
                    responses.append(random.choice(self.REPONSES_ETAT_FR).format(piece=piece_name, etat=et))
            else:
                 responses.append("⚠️ Aucune LED simple trouvée pour votre compte.")

        # LED RGB
        elif act["type"] == "rgb":
            if act.get("action") == "eteins":
                LEDColor.objects.create(user=self.user, r=0, g=0, b=0)
                responses.append("⚫ Lumière RGB éteinte (couleur réglée sur noir).")
            else:
                rgb = extract_rgb(act["raw"])
                if rgb:
                    if rgb == (0,0,0):
                         LEDColor.objects.create(user=self.user, r=0, g=0, b=0)
                         responses.append("⚫ Lumière RGB éteinte (couleur réglée sur noir).")
                    else:
                        LEDColor.objects.create(user=self.user, r=rgb[0], g=rgb[1], b=rgb[2])
                        responses.append(f"🎨 Couleur RGB appliquée : {rgb}.")
                else:
                    responses.append("⚠️ Je n'ai pas compris la couleur demandée.")

        # Capteurs
        elif act["type"] == "capteur":
            dht = DHTData.objects.filter(user=self.user).order_by("-created_at").first()
            soil = SoilData.objects.filter(user=self.user).order_by("-created_at").first()
            air = SensorData.objects.filter(user=self.user).order_by("-timestamp").first()
            morceaux = []
            if dht: morceaux.append(f"🌡️ DHT : {dht.temperature:.1f}°C, {dht.humidity:.0f}%")
            if soil: morceaux.append(f"🌱 Sol : humidité {soil.humidity}%")
            if air: morceaux.append(f"🌬️ Air : CO₂ {air.co2} ppm, Gaz: {air.gaz_type}")

            if morceaux: responses.append(" | ".join(morceaux))
            else: responses.append("⚠️ Aucune donnée capteur récente.")
        # Relais
        elif act["type"] == "relais":
            num = self.RELAIS_MAPPING.get(act["piece"])
            piece_name = act["piece"].capitalize()
            try:
                relais = Relais.objects.get(user=self.user, num=num)
                if act["action"] == "allume":
                    relais.etat = True
                    relais.save()
                    responses.append(random.choice(self.REPONSES_ALLUME_FR).format(piece=piece_name))
                elif act["action"] == "eteins":
                    relais.etat = False
                    relais.save()
                    responses.append(random.choice(self.REPONSES_ETEINS_FR).format(piece=piece_name))
                elif act["action"] == "toggle":
                    relais.etat = not relais.etat
                    relais.save()
                    nouvel = "allumée" if relais.etat else "éteinte"
                    responses.append(random.choice(self.REPONSES_TOGGLE_FR).format(piece=piece_name, nouvel_etat=nouvel))
                else:
                    et = "allumée" if relais.etat else "éteinte"
                    responses.append(random.choice(self.REPONSES_ETAT_FR).format(piece=piece_name, etat=et))
            except Relais.DoesNotExist:
                responses.append(f"⚠️ Relais '{piece_name}' introuvable pour votre compte.")

        return responses

    # -------------------------
    # Réponse globale
    # -------------------------
    def get_response(self, raw_msg):
        msg = normalize(raw_msg)
        responses = []

        # 1. Commandes directes
        if msg in {"stop", "arrête", "stop reading", "urgence"}: return "🛑 ARRÊT D'URGENCE DEMANDÉ."

        if msg == "help_more":
             other_topics = {k: v for k, v in self.HELP_TOPICS.items() if k not in ["1", "2", "4", "5"]}
             buttons = [{"text": f"{k}. {v.split('(')[0].strip()}", "value": k} for k, v in other_topics.items()]
             return {"reponse": "📚 Autres sujets :", "buttons": buttons}

        elif any(m in msg for m in self.INTENT_WORDS["bio"]): responses.append(self.BIO_TEXT)
        elif any(m in msg for m in self.INTENT_WORDS["founatek"]): responses.append(self.FOUNATEK_TEXT)
        elif any(m in msg for m in self.INTENT_WORDS["historique"]):
            hist = self.get_user_history(user=self.user)
            responses.append("🕒 Vos dernières actions :\n" + "\n".join(hist[:15]))

        elif any(m in msg for m in self.INTENT_WORDS["help"]):
            main_topics = {k: v for k, v in self.HELP_TOPICS.items() if k in ["1", "2", "4", "5"]}
            buttons = [{"text": f"{k}. {v.split('(')[0].strip()}", "value": k} for k, v in main_topics.items()]
            buttons.append({"text": "Plus d'aide...", "value": "help_more"})
            return {"reponse": "📚 Voici les sujets principaux :", "buttons": buttons}

        elif msg in self.HELP_RESPONSES:
            responses.append(self.HELP_RESPONSES[msg])

        # 2. Analyse (Locale STRICTE + IA)
        actions = self.parse_actions(raw_msg)

        # SI le parsing local n'a rien trouvé de SÛR, on appelle l'IA.
        # C'est ça qui rend le système "ultra intelligent" : il ne devine plus.
        if self.model and not actions:
            try:
                gemini_response = self.model.generate_content(raw_msg)
                if gemini_response and gemini_response.text:
                    translated_cmd = gemini_response.text.strip()
                    logger.info(f"Gemini translation: '{raw_msg}' -> '{translated_cmd}'")
                    actions += self.parse_actions(translated_cmd)
            except Exception as e:
                logger.error(f"Erreur IA : {e}")

        # 3. Exécution
        unique_responses = set()
        seen_actions = set()
        for act in actions:
            act_signature = (act.get("type"), act.get("piece") or act.get("target"), act.get("action"))
            if act_signature not in seen_actions:
                res_list = self.execute_action(act)
                unique_responses.update(res_list)
                seen_actions.add(act_signature)

        responses.extend(list(unique_responses))

        # 4. Fallback
        if not responses and not isinstance(responses, dict):
            help_summary = "Essayez : 'éteins salon', 'température', 'accès porte', 'éteins rgb'..."
            responses.append(f"🤔 Je n'ai pas compris. {help_summary}\nTapez 'aide' pour plus de détails.")

        final_response = "\n".join([r for r in responses if r])
        return final_response if final_response else "..."