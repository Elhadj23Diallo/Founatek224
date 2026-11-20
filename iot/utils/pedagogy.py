from ..models import Lecon, Progression, Quiz



PASS_SCORE = 70  # score minimum en %


def lecon_precedente(lecon):
    """La leçon juste avant, dans l'ordre global du parcours — en sautant les
    fiches Livre 1 non publiées (brouillons en attente de relecture/quiz) :
    personne ne peut jamais les valider, donc les compter bloquerait pour
    toujours tout ce qui suit, même une fois payé."""
    candidats = Lecon.objects.filter(
        parcours=lecon.parcours,
        ordre__lt=lecon.ordre
    ).select_related("academy_book_entry").order_by('-ordre')
    for candidat in candidats:
        entry = getattr(candidat, "academy_book_entry", None)
        if entry is not None and not entry.published:
            continue
        return candidat
    return None


def lecon_est_debloquee(user, lecon):
    # Première leçon → toujours accessible
    if lecon.ordre == 1:
        return True

    precedente = lecon_precedente(lecon)
    if not precedente:
        return True

    try:
        progression = Progression.objects.get(user=user, lecon=precedente)
        return progression.completed
    except Progression.DoesNotExist:
        return False


def valider_lecon(user, lecon, score):
    progression, _ = Progression.objects.get_or_create(
        user=user,
        lecon=lecon
    )

    progression.score = score
    progression.completed = score >= PASS_SCORE
    progression.save()

    return progression.completed
