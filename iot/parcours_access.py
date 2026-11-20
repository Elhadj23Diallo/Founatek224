"""Contrôle des droits d'accès à un parcours payant (cours formateur).

Distinct du paywall Academy Livre 1 (voir academy_access.py) : ici, n'importe
quel Parcours créé par un formateur peut être payant (prix > 0). Aucun accès
n'est attribué ici : un paiement doit être vérifié côté serveur (webhook
Stripe/PayPal signé) avant de créer un ParcoursAccess actif.
"""
from django.db.models import Q

from .models import ParcoursAccess


def can_read_parcours(user, parcours):
    """Un parcours gratuit (prix <= 0) reste accessible à tous. Un parcours
    payant nécessite d'être son créateur, un admin, ou d'avoir un accès payé actif."""
    if parcours.prix is None or parcours.prix <= 0:
        return True
    if not user or not user.is_authenticated:
        return False
    if user.is_staff or parcours.created_by_id == user.id:
        return True
    return ParcoursAccess.objects.filter(
        user=user, parcours=parcours, active=True, revoked_at__isnull=True
    ).exists()


def readable_parcours_filter(user):
    """Q() utilisable sur un queryset de Lecon (via la FK `parcours`) : vrai si
    le parcours est gratuit, si l'utilisateur est staff/créateur, ou a un
    accès payé actif."""
    free_or_staff = Q(parcours__prix__lte=0)
    if not user or not user.is_authenticated:
        return free_or_staff
    if user.is_staff:
        return Q()
    free_or_staff |= Q(parcours__created_by=user)
    paid_access = Q(
        parcours__accesses__user=user,
        parcours__accesses__active=True,
        parcours__accesses__revoked_at__isnull=True,
    )
    return free_or_staff | paid_access
