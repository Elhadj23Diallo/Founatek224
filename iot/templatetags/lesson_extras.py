import re
from django import template
from django.utils.html import escape
from django.utils.safestring import mark_safe

register = template.Library()

_BOLD_RE = re.compile(r"\*\*([^*]+)\*\*")


@register.filter(name="markdown_lite")
def markdown_lite(value):
    """
    Rendu minimal : convertit **gras** en <strong>, retire les asterisques
    isoles restants, puis transforme les sauts de ligne en <br>/paragraphes.
    """
    if not value:
        return ""
    text = escape(str(value))
    text = _BOLD_RE.sub(r"<strong>\1</strong>", text)
    text = text.replace("*", "")
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    html = "".join(
        f"<p>{p.replace(chr(10), '<br>')}</p>" for p in paragraphs
    ) or f"<p>{text}</p>"
    return mark_safe(html)
