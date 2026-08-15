from decimal import Decimal
from django import template

register = template.Library()


@register.filter
def mul(value, arg):
    try:
        return Decimal(value) * Decimal(arg)
    except Exception:
        return value


@register.filter
def spec_label(line):
    """Retourne la partie avant les ':' d'une ligne 'Label : Valeur'."""
    if ':' in line:
        return line.split(':', 1)[0].strip()
    return line


@register.filter
def spec_value(line):
    """Retourne la partie apres les ':' d'une ligne 'Label : Valeur'."""
    if ':' in line:
        return line.split(':', 1)[1].strip()
    return ''
