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


def search_course_content(query, limit=3, excerpt_len=320):
    """Renvoie les blocs/lecons de cours publies les plus pertinents pour `query`.

    Chaque resultat : {parcours, lecon, excerpt, score}. Liste vide si aucun
    mot-cle significatif ou aucune correspondance — l'appelant doit alors
    laisser le prompt tel quel plutot que d'injecter du contenu non pertinent.
    """
    from iot.models import BlocPedagogique, Lecon

    words = _keywords(query)
    if not words:
        return []

    q_blocs = Q()
    q_lecons = Q()
    for w in words:
        q_blocs |= Q(contenu__icontains=w) | Q(code__icontains=w)
        q_lecons |= Q(titre__icontains=w) | Q(resume__icontains=w)

    candidates = {}

    blocs = (
        BlocPedagogique.objects.filter(q_blocs, lecon__parcours__is_published=True)
        .exclude(type__in=["image", "video"])
        .select_related("lecon", "lecon__parcours")[:50]
    )
    for b in blocs:
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
        Lecon.objects.filter(q_lecons, parcours__is_published=True)
        .select_related("parcours")[:50]
    )
    for l in lecons:
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
