from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from espcontrol.chatbot_evals import run_evals

EVAL_USERNAME = "_chatbot_eval_user"


class Command(BaseCommand):
    help = (
        "Lance les evals qualite du chatbot (vrais appels Groq, non deterministe) — "
        "a utiliser a la main avant de modifier le prompt systeme ou les outils. "
        "Ne fait JAMAIS partie de la suite de tests automatisee."
    )

    def handle(self, *args, **options):
        user, _ = User.objects.get_or_create(
            username=EVAL_USERNAME, defaults={"email": "eval@founatek.local"},
        )
        self._reset_eval_state(user)

        results = run_evals(user)

        self.stdout.write("")
        for r in results:
            icon = self.style.SUCCESS("✔ PASS") if r["passed"] else self.style.ERROR("✘ FAIL")
            self.stdout.write(f"{icon}  {r['name']}")
            if not r["passed"]:
                self.stdout.write(f"       Attendu : {r['detail']}")
                self.stdout.write(f"       Réponse : {r['response'][:200]}")

        passed = sum(1 for r in results if r["passed"])
        total = len(results)
        self.stdout.write("")
        summary = f"{passed}/{total} evals réussis"
        self.stdout.write(self.style.SUCCESS(summary) if passed == total else self.style.WARNING(summary))

        if passed != total:
            raise SystemExit(1)

    def _reset_eval_state(self, user):
        """Repart d'un etat propre a chaque run pour que le resultat ne depende
        jamais d'un residu du run precedent (faux positif si un ancien outil
        avait reussi mais pas celui-ci)."""
        from espcontrol.models import (
            Device, AppareilData, Relais, LEDColor, ChatPreference,
            ChatEscalation, ChatLog,
        )
        Device.objects.filter(user=user).delete()
        AppareilData.objects.filter(device__user=user).delete()
        Relais.objects.filter(user=user).delete()
        LEDColor.objects.filter(user=user).delete()
        ChatPreference.objects.filter(user=user).delete()
        ChatEscalation.objects.filter(user=user).delete()
        ChatLog.objects.filter(user=user).delete()
