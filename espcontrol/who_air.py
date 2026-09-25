"""Classification PM2.5 / PM10 d'apres les lignes directrices OMS 2021.

Source unique utilisee par le tableau de bord web, l'API mobile, le chatbot et
la veilleuse LED, afin que toute la plateforme affiche les memes niveaux.

L'OMS ne definit pas d'indice unique : elle publie une valeur guide (24 h et
annuelle) et des cibles intermediaires (CI 1 a 4). Les 6 niveaux ci-dessous
sont adosses a ces seuils.
"""
from statistics import median

# (borne haute incluse, cle, libelle, couleur, fond, repere OMS, conseil)
_LEVELS = [
    ("excellent", "Excellent", "#047857", "#d1fae5",
     "Sous la valeur guide annuelle OMS",
     "Air de qualité optimale. Aucune précaution particulière."),
    ("bon", "Bon", "#16a34a", "#dcfce7",
     "Conforme à la valeur guide OMS (24 h)",
     "Air conforme aux recommandations de l'OMS. Activités normales."),
    ("modere", "Modéré", "#ca8a04", "#fef9c3",
     "Cible intermédiaire 4 de l'OMS",
     "Acceptable pour la plupart. Les personnes très sensibles peuvent limiter l'effort prolongé en extérieur."),
    ("mediocre", "Médiocre", "#ea580c", "#ffedd5",
     "Cible intermédiaire 3 de l'OMS",
     "Enfants, personnes âgées et asthmatiques : réduire les efforts intenses en extérieur, aérer brièvement."),
    ("mauvais", "Mauvais", "#dc2626", "#fee2e2",
     "Cibles intermédiaires 2 à 1 de l'OMS",
     "Limiter le temps passé dehors, éviter l'effort physique, privilégier les pièces filtrées ou fermées."),
    ("dangereux", "Dangereux", "#7f1d1d", "#fecaca",
     "Au-delà de la cible intermédiaire 1 de l'OMS",
     "Rester à l'intérieur, porter un masque FFP2 si sortie nécessaire, consulter en cas de gêne respiratoire."),
]

# Bornes hautes (incluses) des 5 premiers niveaux, le 6e est ouvert.
_LIMITS = {
    "pm2p5": (5, 15, 25, 37.5, 75),
    "pm10":  (15, 45, 75, 100, 200),
}

# Valeurs guides OMS 2021 (µg/m³).
GUIDELINES = {
    "pm2p5": {"annual": 5,  "h24": 15},
    "pm10":  {"annual": 15, "h24": 45},
}

LEVEL_KEYS = [lv[0] for lv in _LEVELS]


def _num(v):
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def level_index(pollutant, value):
    """Indice du niveau (0..5) ou None si pas de mesure."""
    value = _num(value)
    if value is None:
        return None
    for i, bound in enumerate(_LIMITS[pollutant]):
        if value <= bound:
            return i
    return len(_LEVELS) - 1


def _level_dict(index):
    key, label, color, bg, ref, advice = _LEVELS[index]
    return {"index": index, "key": key, "label": label, "color": color,
            "bg": bg, "ref": ref, "advice": advice}


def classify(pollutant, value):
    """Niveau OMS d'une valeur, ou None."""
    i = level_index(pollutant, value)
    return None if i is None else _level_dict(i)


def scale(pollutant):
    """Echelle complete (pour dessiner la barre) : segments avec bornes."""
    limits = _LIMITS[pollutant]
    out = []
    lo = 0
    for i, lv in enumerate(_LEVELS):
        hi = limits[i] if i < len(limits) else None
        d = _level_dict(i)
        d["lo"], d["hi"] = lo, hi
        out.append(d)
        if hi is not None:
            lo = hi
    return out


def marker_position(pollutant, value):
    """Position 0..100 du curseur sur la barre a 6 segments egaux."""
    value = _num(value)
    if value is None:
        return None
    limits = _LIMITS[pollutant]
    n = len(_LEVELS)
    i = level_index(pollutant, value)
    lo = 0 if i == 0 else limits[i - 1]
    if i < len(limits):
        frac = (value - lo) / (limits[i] - lo)
    else:
        frac = min((value - lo) / lo, 1.0)  # dernier segment : sature a +100 %
    return round(min(max((i + frac) / n * 100, 0), 100), 1)


def _row(pollutant, current, avg24):
    guide = GUIDELINES[pollutant]
    current, avg24 = _num(current), _num(avg24)
    return {
        "pollutant": pollutant,
        "current": None if current is None else round(current, 1),
        "avg24": None if avg24 is None else round(avg24, 1),
        "guide24": guide["h24"],
        "guide_annual": guide["annual"],
        "current_level": classify(pollutant, current),
        "avg24_ok": None if avg24 is None else avg24 <= guide["h24"],
        "ratio24": None if avg24 is None else round(avg24 / guide["h24"], 2),
    }


def device_report(recent, avg24_pm25=None, avg24_pm10=None):
    """Rapport OMS d'un appareil.

    recent : payloads (dict) des dernieres mesures, la plus recente d'abord.
    Le niveau global repose sur la MEDIANE des 5 dernieres mesures (un pic
    isole n'alarme pas) et retient le pire des deux polluants.
    """
    def series(key):
        return [p.get(key) for p in recent
                if isinstance(p, dict) and _num(p.get(key)) is not None][:5]

    latest = recent[0] if recent and isinstance(recent[0], dict) else {}
    pm25_s, pm10_s = series("pm2p5"), series("pm10")
    pm25_med = median(pm25_s) if pm25_s else None
    pm10_med = median(pm10_s) if pm10_s else None

    idx = [i for i in (level_index("pm2p5", pm25_med), level_index("pm10", pm10_med)) if i is not None]
    overall = _level_dict(max(idx)) if idx else None

    pm25, pm10 = _num(latest.get("pm2p5")), _num(latest.get("pm10"))
    fine_ratio = None
    if pm25 is not None and pm10 not in (None, 0):
        fine_ratio = round(min(pm25 / pm10, 1.0) * 100)

    return {
        "overall": overall,
        "pm2p5": _row("pm2p5", pm25, avg24_pm25),
        "pm10": _row("pm10", pm10, avg24_pm10),
        "pm25_marker": marker_position("pm2p5", pm25_med),
        "pm10_marker": marker_position("pm10", pm10_med),
        "fine_ratio": fine_ratio,
        "coarse": None if pm25 is None or pm10 is None else round(max(pm10 - pm25, 0), 1),
        "basis": "médiane des 5 dernières mesures",
    }


def avg_pm_24h(readings_qs):
    """Moyennes PM2.5/PM10 sur un queryset de mesures (agrégat SQL, repli Python)."""
    try:
        from django.db.models import Avg, FloatField
        from django.db.models.fields.json import KeyTextTransform
        from django.db.models.functions import Cast
        agg = readings_qs.aggregate(
            a25=Avg(Cast(KeyTextTransform('pm2p5', 'payload'), FloatField())),
            a10=Avg(Cast(KeyTextTransform('pm10', 'payload'), FloatField())),
        )
        return {"avg_pm25": agg["a25"], "avg_pm10": agg["a10"]}
    except Exception:
        def avg(key):
            v = [r.payload.get(key) for r in readings_qs
                 if r.payload and isinstance(r.payload.get(key), (int, float))]
            return sum(v) / len(v) if v else None
        return {"avg_pm25": avg('pm2p5'), "avg_pm10": avg('pm10')}
