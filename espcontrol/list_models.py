from google import genai

client = genai.Client(api_key="AIzaSyCO8uhWDYpKD02JBoBseWOO_Qq9bzRT0UE")

def lister_modeles():
    for m in client.models.list():
        print("Modèle :", m.name, "| actions supportées:", m.supported_actions)

if __name__ == "__main__":
    lister_modeles()
