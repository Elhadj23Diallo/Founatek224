# intents.py

RELAIS_MAPPING = {"salon": 1, "chambre": 2, "garage": 3}

INTENT_WORDS = {
    "on": {"allume", "allumer", "active", "mets", "mettre"},
    "off": {"eteins", "éteins", "eteindre", "éteindre", "coupe", "désactive"},
    "toggle": {"bascule", "toggle", "inverse"},
    "etat": {"etat", "état", "status", "statut", "allumee", "allumé", "eteint", "éteint"},
    "capteurs": {"capteur", "capteurs", "temperature", "température", "humidite", "humidité", "co2", "gaz", "air", "sol", "dht"},
    "rgb": {"rgb", "couleur", "color", "ws2812", "neopixel"},
    "led_simple": {"led"},
    "bio": {"qui est elhadj", "cest qui elhadj", "elhadj diallo"},
    "founatek": {"founatek", "founa", "founatek iot", "plateforme iot", "application iot"},
    "help": {"aide", "help", "assistance"},
}

REPONSES_ALLUME_FR = ["✅ {piece} allumée !", "✨ {piece} est maintenant éclairée.", "💡 {piece} activée."]
REPONSES_ETEINS_FR = ["💤 {piece} éteinte.", "🌙 {piece} est maintenant à l’arrêt.", "🛑 {piece} désactivée."]
REPONSES_TOGGLE_FR = ["↔️ {piece} basculée : {nouvel_etat}.", "🔁 {piece} → {nouvel_etat}.", "✅ Changement appliqué : {piece} {nouvel_etat}."]
REPONSES_ETAT_FR = ["ℹ️ {piece} est actuellement {etat}.", "📟 Statut {piece} : {etat}.", "✅ {piece} → {etat}."]

BIO_TEXT = "Elhadj Abdourahmane Diallo est développeur et électronicien..."
FOUNATEK_TEXT = "Founatek IoT est une plateforme de gestion et de contrôle d'appareils connectés..."

HELP_TOPICS = {
    "1": "Comment allumer ou éteindre un relais ?",
    "2": "Comment lire les données des capteurs ?",
    "3": "Comment changer la couleur des LED RGB ?",
    "4": "Que fait Founatek IoT ?",
    "5": "Qui est Elhadj Abdourahmane Diallo ?",
    "6": "Mon Token API et mes URLs personnalisées"
}

HELP_RESPONSES = {
    "1": "Pour allumer ou éteindre un relais, tape par exemple : 'allume le salon' ou 'éteins le garage'.",
    "2": "Pour lire les données des capteurs, tape simplement 'capteurs'.",
    "3": "Pour changer la couleur des LED RGB, tape 'mets la lumière en rouge' ou 'rgb(255,0,0)'.",
    "4": FOUNATEK_TEXT,
    "5": BIO_TEXT
}
