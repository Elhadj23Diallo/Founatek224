from ..models import Lecon, Progression, Quiz
from django.utils import timezone
from .pdf import generer_certificat_pdf

CERTIFICATION_MIN_SCORE = 70


def calculer_score_parcours(user, parcours):
    lecons = Lecon.objects.filter(parcours=parcours)
    progressions = Progression.objects.filter(user=user, lecon__in=lecons)

    if progressions.count() != lecons.count():
        return None  # parcours incomplet

    total = sum(p.score for p in progressions)
    return total / progressions.count()


def parcours_est_certifiable(user, parcours):
    if not parcours.certifiant:
        return False

    score = calculer_score_parcours(user, parcours)
    if score is None:
        return False

    return score >= CERTIFICATION_MIN_SCORE




from django.utils import timezone
from .pdf import generer_certificat_pdf


def ensure_certificat_pdf(certification):
    if certification.pdf and certification.pdf_generated_at:
        return

    relative_path = generer_certificat_pdf(certification)

    certification.pdf.name = relative_path
    certification.pdf_generated_at = timezone.now()
    certification.save(update_fields=["pdf", "pdf_generated_at"])
