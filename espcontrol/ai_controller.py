import google.generativeai as genai
from django.conf import settings
import json
import re

# Configuration de l'IA
genai.configure(api_key=settings.GEMINI_API_KEY)

def analyze_iot_command(command_text, user_relais):
    """
    user_relais: Liste des relais de l'utilisateur [{'num': 1, 'nom': 'Salon'}, ...]
    """
    
    # On prépare la liste des appareils pour que l'IA sache ce qui existe
    devices_list_str = ", ".join([f"{r['nom']} (ID: {r['num']})" for r in user_relais])

    prompt = f"""
    Tu es un assistant domotique intelligent.
    Voici les appareils disponibles : [{devices_list_str}].
    
    L'utilisateur dit : "{command_text}"
    
    Règles :
    1. Identifie quel appareil est visé par son nom (même approximatif).
    2. Identifie l'action : "on" (allumer/ouvrir), "off" (éteindre/fermer), "toggle" (inverser).
    3. Si la commande est dangereuse (ex: "tout casser", "surchauffe"), mets "safe": false.
    
    Réponds UNIQUEMENT en JSON strict, sans Markdown, comme ceci :
    {{
        "safe": true,
        "message": "J'allume le salon",
        "relais_num": 1, 
        "action": "on"
    }}
    
    Si aucun appareil ne correspond ou si c'est hors sujet, mets "relais_num": null.
    """

    try:
        model = genai.GenerativeModel('gemini-pro')
        response = model.generate_content(prompt)
        
        # Nettoyage de la réponse pour éviter les ```json ... ```
        clean_text = re.sub(r'```json|```', '', response.text).strip()
        
        return json.loads(clean_text)
    except Exception as e:
        print(f"Erreur IA: {e}")
        return {"safe": False, "message": "Erreur de traitement IA", "relais_num": None}