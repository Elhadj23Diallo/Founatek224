"""Envoie par email le rapport quotidien des conversations chatbot au(x)
fondateur(s) — a brancher sur une tache planifiee PythonAnywhere (quotidienne,
ex. 23:55) :  python manage.py send_daily_chat_report

Par defaut, traite la journee d'HIER (la tache tourne apres minuit pour un
recap complet de la veille) ; --date AAAA-MM-JJ pour une autre journee.
"""
from datetime import datetime

from django.conf import settings
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.core.management.base import BaseCommand
from django.utils import timezone

from espcontrol.chat_reports import build_daily_report, render_report_text


class Command(BaseCommand):
    help = "Envoie le rapport quotidien du chatbot (conversations + demandes transmises) par email."

    def add_arguments(self, parser):
        parser.add_argument("--date", help="Journee a rapporter (AAAA-MM-JJ), defaut hier")

    def handle(self, *args, **options):
        if options.get("date"):
            day = datetime.strptime(options["date"], "%Y-%m-%d").date()
        else:
            day = timezone.localdate() - timezone.timedelta(days=1)

        recipients = list(
            User.objects.filter(is_superuser=True, is_active=True)
            .exclude(email="").values_list("email", flat=True)
        )
        if not recipients and settings.DEFAULT_FROM_EMAIL:
            recipients = [settings.DEFAULT_FROM_EMAIL]
        if not recipients:
            self.stdout.write(self.style.ERROR("Aucun destinataire (aucun superuser avec email)."))
            return

        report = build_daily_report(day)
        body = render_report_text(report)
        subject = (
            f"[Founatek Nexus] Rapport chatbot du {day:%d/%m/%Y} — "
            f"{report['total_messages']} message(s), {report['escalation_count']} à traiter"
        )

        send_mail(
            subject=subject,
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=recipients,
            fail_silently=False,
        )
        self.stdout.write(self.style.SUCCESS(f"✅ Rapport du {day} envoyé à {', '.join(recipients)}."))
