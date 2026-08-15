import google.generativeai as genai

# Configuration de l'API avec votre clé
genai.configure(api_key="AIzaSyCO8uhWDYpKD02JBoBseWOO_Qq9bzRT0UE")

# Liste des modèles disponibles
models = list(genai.list_models())  # <- on convertit le générateur en liste
print(models)
