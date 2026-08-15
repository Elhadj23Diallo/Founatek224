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
