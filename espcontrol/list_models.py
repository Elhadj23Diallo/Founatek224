import os
from google import genai

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY", ""))

def lister_modeles():
    for m in client.models.list():
        print("Modèle :", m.name, "| actions supportées:", m.supported_actions)

if __name__ == "__main__":
    lister_modeles()
