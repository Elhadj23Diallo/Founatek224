import os
import google.generativeai as genai

# Configuration de l'API avec votre clé
genai.configure(api_key=os.getenv("GEMINI_API_KEY", ""))

# Liste des modèles disponibles
models = list(genai.list_models())  # <- on convertit le générateur en liste
print(models)
