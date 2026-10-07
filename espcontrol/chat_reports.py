"""Rapport quotidien des conversations chatbot pour le fondateur.

Agrege les ChatLog (chaque tour question/reponse, site + mobile) et les
ChatEscalation (demandes transmises au service competent) d'une journee,
groupes par utilisateur — utilise par la vue chatbot_daily_report et par la
commande d'envoi email quotidien.
"""
from django.utils import timezone


def _day_bounds(day):
    """Bornes [debut, fin) du jour `day` (date) dans le fuseau local du projet."""
    tz = timezone.get_current_timezone()
    start = timezone.make_aware(timezone.datetime.combine(day, timezone.datetime.min.time()), tz)
    return start, start + timezone.timedelta(days=1)


def build_daily_report(day):
    """Rapport complet d'une journee : KPI, escalades, conversations groupees par utilisateur."""
    from .models import ChatLog, ChatEscalation

    start, end = _day_bounds(day)
    logs = list(
        ChatLog.objects.filter(created_at__gte=start, created_at__lt=end)
        .select_related("user").order_by("created_at")
    )
    escalations = list(
        ChatEscalation.objects.filter(created_at__gte=start, created_at__lt=end)
        .select_related("user", "user__account_profile").order_by("-created_at")
    )

    by_user = {}
    for log in logs:
        by_user.setdefault(log.user, []).append(log)

    conversations = [
        {"user": user, "turns": turns, "count": len(turns), "escalations": sum(1 for t in turns if t.escalated)}
        for user, turns in sorted(by_user.items(), key=lambda kv: -len(kv[1]))
    ]

    return {
        "day": day,
        "total_messages": len(logs),
        "unique_users": len(by_user),
        "web_count": sum(1 for l in logs if l.channel == "web"),
        "mobile_count": sum(1 for l in logs if l.channel == "mobile"),
        "escalation_count": len(escalations),
        "escalations": escalations,
        "conversations": conversations,
        "proactive_count": sum(1 for l in logs if l.proactive),
        "up_count": sum(1 for l in logs if l.rating == "up"),
        "down_count": sum(1 for l in logs if l.rating == "down"),
    }


def render_report_text(report):
    """Version texte brut (pour l'email quotidien)."""
    lines = [
        f"Rapport chatbot Founatek Nexus — {report['day']:%d/%m/%Y}",
        "=" * 48,
        f"Messages échangés : {report['total_messages']} (site : {report['web_count']}, mobile : {report['mobile_count']})",
        f"Utilisateurs actifs : {report['unique_users']}",
        f"Demandes transmises au service compétent : {report['escalation_count']}",
        f"Messages proactifs envoyés (alertes) : {report['proactive_count']}",
        f"Avis des utilisateurs : 👍 {report['up_count']} · 👎 {report['down_count']}",
        "",
    ]
    if report["escalations"]:
        lines.append("— Demandes à traiter —")
        for e in report["escalations"]:
            phone = getattr(getattr(e.user, "account_profile", None), "phone", None)
            lines.append(
                f"  [{e.get_category_display()}] {e.user.username} "
                f"(email: {e.user.email or '—'}, tel: {phone or '—'}) — {e.summary}"
            )
        lines.append("")

    lines.append("— Conversations par utilisateur —")
    for conv in report["conversations"]:
        lines.append(f"\n{conv['user'].username} ({conv['count']} message(s)) :")
        for t in conv["turns"]:
            marker = " [ESCALADÉ]" if t.escalated else ""
            marker += " [PROACTIF]" if t.proactive else ""
            marker += " 👍" if t.rating == "up" else (" 👎" if t.rating == "down" else "")
            lines.append(f"  · {timezone.localtime(t.created_at):%H:%M} — Q: {t.message}")
            lines.append(f"            R: {t.response}{marker}")

    return "\n".join(lines)
