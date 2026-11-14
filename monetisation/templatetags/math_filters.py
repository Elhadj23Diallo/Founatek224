from django import template

register = template.Library()

@register.filter
def div(value, arg):
    try:
        return value / arg
    except:
        return 0

@register.filter
def mul(value, arg):
    try:
        return value * arg
    except:
        return 0

@register.filter
def thousands(value):
    """Formate un nombre avec des espaces comme séparateurs de milliers (ex: 200000 -> 200 000)."""
    try:
        return f"{int(value):,}".replace(",", " ")
    except (TypeError, ValueError):
        return value
