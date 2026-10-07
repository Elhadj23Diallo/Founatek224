"""Evals du chatbot NEXUS — contrairement a test_chat_report.py (qui mocke
Groq pour tester le CODE autour), ces cas appellent le vrai modele pour
verifier la QUALITE des reponses : groundedness, bon usage des outils,
anti-hallucination, escalade. A lancer a la main avant de modifier le prompt
systeme ou les outils (jamais dans la suite de tests automatisee — coute de
vrais appels API et le modele n'est pas deterministe).

Usage : python manage.py run_chatbot_evals
"""
from dataclasses import dataclass, field
from typing import Callable

from .models import Relais, LEDColor, ChatPreference


@dataclass
class EvalCase:
    name: str
    message: str
    setup: Callable[["Chatbot"], None] = field(default=lambda bot: None)  # noqa: F821
    check: Callable[[str, "Chatbot"], tuple] = field(default=lambda resp, bot: (True, ""))  # noqa: F821


def _seed_air_quality(bot, pm25=12.3, pm10=18.0):
    from .models import Device, AppareilData
    device, _ = Device.objects.get_or_create(
        user=bot.user, device_id="EVAL_DEVICE", defaults={"name": "Capteur Eval", "is_active": True},
    )
    device.is_active = True
    device.save()
    AppareilData.objects.create(device=device, payload={"pm2p5": pm25, "pm10": pm10})


def _seed_relais_salon(bot, etat=True):
    from .models import Relais
    Relais.objects.update_or_create(user=bot.user, num=1, defaults={"nom": "Salon", "etat": etat})


def _seed_ohm_lesson(bot):
    from iot.models import Organisation, Parcours, Lecon, BlocPedagogique
    org, _ = Organisation.objects.get_or_create(nom="Eval Org")
    parcours, _ = Parcours.objects.get_or_create(
        organisation=org, created_by=bot.user, titre="Arduino eval",
        defaults={"description": "x", "niveau": "Débutant", "is_published": True},
    )
    parcours.is_published = True
    parcours.save()
    lecon, _ = Lecon.objects.get_or_create(parcours=parcours, titre="La loi d'Ohm", defaults={"ordre": 1})
    BlocPedagogique.objects.get_or_create(
        lecon=lecon, type="texte", ordre=1,
        defaults={"contenu": "La loi d'Ohm relie tension U, courant I et resistance R : U = R x I."},
    )


def _contains_number(text, value, tolerance=0.5):
    import re
    for m in re.findall(r"\d+[.,]?\d*", text):
        try:
            if abs(float(m.replace(",", ".")) - value) <= tolerance:
                return True
        except ValueError:
            continue
    return False


EVAL_CASES = [
    EvalCase(
        name="air_quality_grounded",
        message="Comment est l'air chez moi en ce moment ?",
        setup=lambda bot: _seed_air_quality(bot, pm25=12.3),
        check=lambda resp, bot: (
            _contains_number(resp, 12.3),
            "Doit citer la vraie valeur PM2.5 (12.3), pas une valeur inventée.",
        ),
    ),
    EvalCase(
        name="no_hallucination_without_data",
        message="Quelle est la qualité de l'air chez moi ?",
        check=lambda resp, bot: (
            not _contains_number(resp, 0, tolerance=999) or any(
                w in resp.lower() for w in ["aucune", "pas de donnée", "pas de données", "introuvable", "capteur"]
            ),
            "Sans aucune mesure, ne doit pas inventer un chiffre — doit dire qu'il n'a pas la donnée.",
        ),
    ),
    EvalCase(
        name="relais_tool_call_natural_language",
        message="Tu peux assombrir un peu le salon stp ?",
        setup=lambda bot: _seed_relais_salon(bot, etat=True),
        check=lambda resp, bot: (
            (lambda r: r is not None and r.etat is False)(Relais.objects.filter(user=bot.user, num=1).first()),
            "La demande indirecte doit déclencher l'outil set_relais et éteindre le relais Salon.",
        ),
    ),
    EvalCase(
        name="led_ambiance_tool_call",
        message="Mets une ambiance cosy sur la LED stp",
        check=lambda resp, bot: (
            (lambda c: c is not None and (c.r, c.g, c.b) != (0, 0, 0))(LEDColor.objects.filter(user=bot.user).first()),
            "Doit appeler set_led avec une couleur non nulle.",
        ),
    ),
    EvalCase(
        name="escalation_for_refund_request",
        message="Je veux être remboursé de mon abonnement, c'est inadmissible !",
        check=lambda resp, bot: (
            bot.last_escalated and "transmise" in resp.lower(),
            "Une demande de remboursement doit être transmise au service compétent, jamais traitée par l'IA elle-même.",
        ),
    ),
    EvalCase(
        name="remember_preference_tool_call",
        message="À partir de maintenant, appelle-moi Capitaine stp.",
        check=lambda resp, bot: (
            ChatPreference.objects.filter(user=bot.user, value__icontains="capitaine").exists(),
            "Doit appeler remember_preference et stocker 'Capitaine'.",
        ),
    ),
    EvalCase(
        name="course_rag_grounded",
        message="Explique-moi comment fonctionne la loi d'Ohm.",
        setup=_seed_ohm_lesson,
        check=lambda resp, bot: (
            "ohm" in resp.lower(),
            "Doit s'appuyer sur le contenu de la leçon récupérée par le RAG.",
        ),
    ),
]


def run_evals(user, cases=None, delay_seconds=6):
    """Execute chaque cas contre un vrai appel au chatbot (Groq inclus).
    Renvoie une liste de dicts {name, passed, detail, response}.

    delay_seconds : pause entre chaque cas pour rester sous la limite de
    debit du plan Groq gratuit (sinon des 429 font echouer des cas valides)."""
    import time

    from .chatbot_model import Chatbot

    results = []
    for i, case in enumerate(cases or EVAL_CASES):
        if i > 0 and delay_seconds:
            time.sleep(delay_seconds)
        bot = Chatbot(user)
        case.setup(bot)
        try:
            response = bot.get_response(case.message, channel="web")
            text = response.get("reponse", "") if isinstance(response, dict) else str(response)
            passed, detail = case.check(text, bot)
        except Exception as e:
            passed, detail, text = False, f"Exception : {e}", ""
        results.append({"name": case.name, "passed": bool(passed), "detail": detail, "response": text})
    return results
