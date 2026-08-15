from ..models import Lecon, Progression, Quiz



PASS_SCORE = 70  # score minimum en %


def lecon_precedente(lecon):
    return Lecon.objects.filter(
        parcours=lecon.parcours,
        ordre__lt=lecon.ordre
    ).order_by('-ordre').first()


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
