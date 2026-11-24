"""Recherche legere (mots-cles, sans embeddings) dans le contenu des cours
Education IoT, pour ancrer les reponses du chatbot sur le vrai contenu
pedagogique au lieu de generaliser. Suffisant pour le volume de contenu de
la plateforme et sans dependance ni cout supplementaire (SQL simple)."""
import re

from django.db.models import Q

from .utils import normalize

_STOPWORDS = {
    "les", "des", "une", "un", "le", "la", "de", "du", "et", "est", "pour",
    "dans", "sur", "que", "qui", "quoi", "avec", "sans", "comment", "pourquoi",
    "quand", "quel", "quelle", "quels", "quelles", "mon", "ma", "mes", "ton",
    "ta", "tes", "son", "sa", "ses", "ce", "cette", "ces", "je", "tu", "il",
    "elle", "nous", "vous", "ils", "elles", "peux", "peut", "faire", "faut",
}


def _keywords(text):
    words = re.findall(r"[a-zàâäéèêëîïôöùûüç0-9]+", normalize(text))
    return [w for w in words if len(w) >= 3 and w not in _STOPWORDS]


def search_course_content(query, limit=3, excerpt_len=320, *, user=None):
    """Renvoie les blocs/lecons de cours publies les plus pertinents pour `query`.

    Chaque resultat : {parcours, lecon, excerpt, score}. Liste vide si aucun
    mot-cle significatif ou aucune correspondance — l'appelant doit alors
    laisser le prompt tel quel plutot que d'injecter du contenu non pertinent.
    """
    from iot.models import BlocPedagogique, Lecon
    from iot.academy_access import filter_readable_lessons, has_full_access, raw_book_draft_q
    from iot.utils.pedagogy import lecon_est_debloquee, lecon_precedente

    words = _keywords(query)
    if not words:
        return []

    q_blocs = Q()
    q_lecons = Q()
    for w in words:
        q_blocs |= Q(contenu__icontains=w) | Q(code__icontains=w)
        q_lecons |= Q(titre__icontains=w) | Q(resume__icontains=w)

    # Apply the same lesson-level entitlements as Academy before extracting text.
    # Without a user, only public/free content can be searched.
    readable = filter_readable_lessons(
        Lecon.objects.filter(parcours__is_published=True).exclude(raw_book_draft_q()), user
    ).values('pk')
    candidates = {}
    staff = has_full_access(user)

    def unlocked(lesson):
        if staff:
            return True
        if not getattr(user, "is_authenticated", False):
            return lesson.ordre == 1 or lecon_precedente(lesson) is None
        return lecon_est_debloquee(user, lesson)

    blocs = (
        BlocPedagogique.objects.filter(q_blocs, lecon_id__in=readable)
        .exclude(type__in=["image", "video"])
        .select_related("lecon", "lecon__parcours")[:50]
    )
    for b in blocs:
        if not unlocked(b.lecon):
            continue
        text = normalize(f"{b.lecon.titre} {b.contenu or ''} {b.code or ''}")
        score = sum(text.count(w) for w in words)
        if score <= 0:
            continue
        key = b.lecon_id
        excerpt = (b.contenu or b.code or "").strip()[:excerpt_len]
        if key not in candidates or score > candidates[key]["score"]:
            candidates[key] = {
                "parcours": b.lecon.parcours.titre,
                "lecon": b.lecon.titre,
                "excerpt": excerpt,
                "score": score,
            }

    lecons = (
        Lecon.objects.filter(q_lecons, pk__in=readable)
        .select_related("parcours")[:50]
    )
    for l in lecons:
        if not unlocked(l):
            continue
        text = normalize(f"{l.titre} {l.resume or ''}")
        score = sum(text.count(w) for w in words)
        if score <= 0:
            continue
        key = l.id
        if key not in candidates or score > candidates[key]["score"]:
            candidates.setdefault(key, {
                "parcours": l.parcours.titre,
                "lecon": l.titre,
                "excerpt": (l.resume or "").strip()[:excerpt_len],
                "score": score,
            })

    ranked = sorted(candidates.values(), key=lambda r: -r["score"])
    return ranked[:limit]


def format_course_context(results):
    if not results:
        return ""
    lines = ["CONTENU DE COURS PERTINENT (cite le nom de la lecon si tu t'en sers) :"]
    for r in results:
        lines.append(f"- [{r['parcours']} > {r['lecon']}] {r['excerpt']}")
    return "\n".join(lines)
