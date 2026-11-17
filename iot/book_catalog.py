"""Catalogue du Livre 1 Founatek Academy.

Source de vérité pour l'ordre des chapitres et la tarification.
Ce module ne crée ni commande ni accès payant. L'activation commerciale
nécessite un paiement confirmé et un droit d'accès persistant.
"""
from decimal import Decimal

BOOK_SLUG = "catalogue-electronique-embarquee-livre-1"
PACK_PRICE_EUR = Decimal("9.99")
FREE_CHAPTER = "00"
CHAPTERS = (
    ("00", "Les bases", True),
    ("01", "Composants passifs", False),
    ("02", "Semi-conducteurs", False),
    ("03", "Circuits intégrés", False),
    ("04", "Cartes de développement", False),
    ("05", "Alimentation et énergie", False),
    ("06", "Entrées et commandes", False),
    ("07", "Capteurs", False),
    ("08", "Actionneurs", False),
    ("09", "Affichage", False),
    ("10", "Communication", False),
    ("11", "Outils de l'électronicien", False),
)


def chapter_is_free(chapter_number):
    """Fail closed: un numéro inconnu n'est jamais déclaré gratuit."""
    return str(chapter_number).zfill(2) == FREE_CHAPTER


def ordered_chapters():
    return tuple(
        {"number": number, "title": title, "is_free": is_free}
        for number, title, is_free in CHAPTERS
    )
