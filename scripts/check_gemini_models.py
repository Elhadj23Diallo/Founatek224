"""Liste les modèles Gemini accessibles avec la clé GEMINI_API_KEY.

À lancer à la main : python scripts/check_gemini_models.py
(Ce n'est pas un test : il appelle l'API Gemini et ne doit pas tourner
pendant « python manage.py test ».)
"""
import os


def main():
    import google.generativeai as genai

    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        raise SystemExit("GEMINI_API_KEY absente : ajoute-la dans le .env.")
    genai.configure(api_key=api_key)
    for model in genai.list_models():
        print(model.name, "|", ", ".join(model.supported_generation_methods))


if __name__ == "__main__":
    main()
