"""Remboursements et litiges des contenus numériques : pack Livre 1 et parcours payants.

Règles (appliquées par les webhooks Stripe et PayPal signés) :
- remboursement total : le paiement passe en « refunded » et l'accès est retiré ;
- remboursement partiel : l'accès est gardé, l'admin est prévenu ;
- litige ouvert : l'accès est suspendu (paiement « disputed ») ;
- litige gagné : l'accès est rendu ; litige perdu : il reste retiré.
Chaque fonction est idempotente (un même événement reçu deux fois ne change rien
la seconde fois) et ne touche que l'accès accordé par CE paiement : si le client
a racheté ensuite, son nouvel accès n'est pas retiré.
"""
import logging

from django.db import transaction
from django.utils import timezone

from iot.models import AcademyPackAccess, AcademyPackPayment, ParcoursAccess, ParcoursPayment

logger = logging.getLogger(__name__)

MODELS = {"academy": AcademyPackPayment, "parcours": ParcoursPayment}


def find_content_payment(provider, reference=None, checkout_id=None):
    """Retrouve un paiement de contenu : ("academy" | "parcours", paiement) ou (None, None)."""
    for kind, model in MODELS.items():
        qs = model.objects.filter(provider=provider)
        payment = qs.filter(payment_reference=reference).first() if reference else None
        if payment is None and checkout_id:
            payment = qs.filter(checkout_id=checkout_id).first()
        if payment is not None:
            return kind, payment
    return None, None


def _accesses(kind, payment):
    refs = [ref for ref in (payment.payment_reference, payment.checkout_id) if ref]
    if kind == "academy":
        return AcademyPackAccess.objects.filter(
            user_id=payment.user_id, pack_slug=payment.pack_slug, payment_reference__in=refs
        )
    return ParcoursAccess.objects.filter(
        user_id=payment.user_id, parcours_id=payment.parcours_id, payment_reference__in=refs
    )


def _label(kind, payment):
    if kind == "academy":
        return "le pack Livre 1"
    return f"le parcours « {payment.parcours.titre} »"


def _alert(subject, body):
    from .refunds import send_admin_alert
    transaction.on_commit(lambda: send_admin_alert(subject, body))


def revoke_content_access(kind, payment_id, new_status, source, detail=""):
    """Remboursement total (new_status="refunded") ou litige ouvert ("disputed")."""
    allowed_from = {"refunded": {"success", "disputed"}, "disputed": {"success"}}[new_status]
    with transaction.atomic():
        payment = MODELS[kind].objects.select_for_update().get(pk=payment_id)
        if payment.status not in allowed_from:
            return False
        payment.status = new_status
        payment.save(update_fields=["status"])
        revoked = _accesses(kind, payment).filter(active=True).update(active=False, revoked_at=timezone.now())
        what = "remboursé" if new_status == "refunded" else "contesté (litige ouvert)"
        _alert(
            f"Accès retiré — {payment.user.username}",
            f"Paiement {source} {what} pour {_label(kind, payment)} ({payment.amount_eur} €).\n"
            f"Accès retiré : {'oui' if revoked else 'aucun accès actif lié à ce paiement'}.\n{detail}",
        )
    logger.info("Accès %s retiré (%s, paiement %s)", kind, new_status, payment_id)
    return True


def close_content_dispute(kind, payment_id, won, source):
    """Litige terminé : gagné, l'accès est rendu ; perdu, il reste retiré."""
    with transaction.atomic():
        payment = MODELS[kind].objects.select_for_update().get(pk=payment_id)
        if payment.status != "disputed":
            return False
        if won:
            payment.status = "success"
            _accesses(kind, payment).update(active=True, revoked_at=None)
        else:
            payment.status = "refunded"
        payment.save(update_fields=["status"])
        _alert(
            f"Litige {source} terminé — {payment.user.username}",
            f"Litige {'gagné : accès rendu' if won else 'perdu : accès définitivement retiré'} "
            f"pour {_label(kind, payment)} ({payment.amount_eur} €).",
        )
    return True


def partial_refund_alert(kind, payment, refunded_label, source):
    _alert(
        f"Remboursement partiel — {payment.user.username}",
        f"Remboursement partiel {source} ({refunded_label}) pour {_label(kind, payment)} "
        f"({payment.amount_eur} €). L'accès est conservé ; retire-le dans l'admin si besoin.",
    )
