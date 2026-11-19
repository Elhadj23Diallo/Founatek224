import re
from django import template
from django.utils.html import escape
from django.utils.safestring import mark_safe

register = template.Library()

_BOLD_RE = re.compile(r"\*\*([^*]+)\*\*")
_CODE_RE = re.compile(r"`([^`]+)`")
_LINK_RE = re.compile(r"\[([^\]]+)\]\(((?:https?://|/)[^\s)]+)\)")
_IMAGE_RE = re.compile(r"^!\[([^\]]*)\]\(((?:https?://|/)[^\s)]+)\)$")
_HEADING_RE = re.compile(r"^(#{1,4})\s+(.+)$")
_BULLET_RE = re.compile(r"^\s*(?:[-*•])\s+(.+)$")
_NUMBERED_RE = re.compile(r"^\s*\d+[.)]\s+(.+)$")
_TABLE_SEP_RE = re.compile(r"^\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?$")

# Encadrés : une ligne « > 💡 … » devient un encadré « astuce », etc.
_CALLOUTS = (
    ("⚠️", "warning"),
    ("⚠", "warning"),
    ("💡", "tip"),
    ("✅", "success"),
    ("🔒", "safety"),
    ("📌", "note"),
)


def _inline(text):
    """Mise en forme d'une ligne déjà échappée : `code`, **gras**, liens.
    Les formules \\( … \\) et $$ … $$ sont laissées telles quelles pour MathJax."""
    codes = []

    def keep_code(match):
        codes.append(match.group(1))
        return f"\x00{len(codes) - 1}\x00"

    text = _CODE_RE.sub(keep_code, text)
    text = _BOLD_RE.sub(r"<strong>\1</strong>", text)
    text = _LINK_RE.sub(r'<a href="\2" target="_blank" rel="noopener">\1</a>', text)
    # Astérisques isolés (restes de mise en forme) retirés, comme avant.
    text = text.replace("*", "")
    for i, code in enumerate(codes):
        text = text.replace(f"\x00{i}\x00", f"<code>{code}</code>")
    return text


def _table(rows):
    cells = [[c.strip() for c in row.strip().strip("|").split("|")] for row in rows]
    head, body = cells[0], cells[1:]
    html = ['<div class="lesson-table-wrap"><table class="lesson-table"><thead><tr>']
    html += [f"<th>{_inline(c)}</th>" for c in head]
    html.append("</tr></thead><tbody>")
    for row in body:
        html.append("<tr>" + "".join(f"<td>{_inline(c)}</td>" for c in row) + "</tr>")
    html.append("</tbody></table></div>")
    return "".join(html)


@register.filter(name="markdown_lite")
def markdown_lite(value):
    """Rendu Markdown simple et sûr pour les leçons (tout est échappé) :
    titres #, listes - / 1., tableaux |…|, encadrés > 💡, formules $$ … $$
    (MathJax), images ![légende](/media/…), `code`, **gras**, liens.
    Un texte sans aucune de ces marques s'affiche comme avant : paragraphes
    séparés par une ligne vide, retours à la ligne conservés."""
    if not value:
        return ""
    lines = escape(str(value)).replace("\r\n", "\n").split("\n")
    out = []
    paragraph = []
    i = 0

    def flush_paragraph():
        if paragraph:
            out.append("<p>" + "<br>".join(_inline(p) for p in paragraph) + "</p>")
            paragraph.clear()

    while i < len(lines):
        line = lines[i].rstrip()
        stripped = line.strip()

        if not stripped:
            flush_paragraph()
            i += 1
            continue

        heading = _HEADING_RE.match(stripped)
        if heading:
            flush_paragraph()
            level = min(len(heading.group(1)) + 2, 6)  # ## -> h4 (le titre de la leçon est au-dessus)
            out.append(f'<h{level} class="lesson-h">{_inline(heading.group(2))}</h{level}>')
            i += 1
            continue

        if stripped.startswith("$$") and stripped.endswith("$$") and len(stripped) > 4:
            flush_paragraph()
            out.append(f'<div class="academy-formula">{stripped}</div>')
            i += 1
            continue

        image = _IMAGE_RE.match(stripped)
        if image:
            flush_paragraph()
            alt, src = image.group(1), image.group(2)
            caption = f"<figcaption>{_inline(alt)}</figcaption>" if alt else ""
            out.append(f'<figure class="lesson-figure"><img src="{src}" alt="{alt}" loading="lazy">{caption}</figure>')
            i += 1
            continue

        if stripped.startswith("|") and i + 1 < len(lines) and _TABLE_SEP_RE.match(lines[i + 1].strip()):
            flush_paragraph()
            rows = [stripped]
            i += 2
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append(lines[i].strip())
                i += 1
            out.append(_table(rows))
            continue

        if _BULLET_RE.match(line) or _NUMBERED_RE.match(line):
            flush_paragraph()
            ordered = bool(_NUMBERED_RE.match(line)) and not _BULLET_RE.match(line)
            pattern = _NUMBERED_RE if ordered else _BULLET_RE
            items = []
            while i < len(lines) and pattern.match(lines[i]):
                items.append(_inline(pattern.match(lines[i]).group(1)))
                i += 1
            tag = "ol" if ordered else "ul"
            out.append(f'<{tag} class="lesson-list">' + "".join(f"<li>{it}</li>" for it in items) + f"</{tag}>")
            continue

        if stripped.startswith("&gt;"):
            flush_paragraph()
            quote = []
            while i < len(lines) and lines[i].strip().startswith("&gt;"):
                quote.append(lines[i].strip()[4:].strip())
                i += 1
            kind = "note"
            for emoji, name in _CALLOUTS:
                if quote and quote[0].startswith(emoji):
                    kind = name
                    break
            out.append(f'<div class="lesson-callout lesson-callout-{kind}">' + "<br>".join(_inline(q) for q in quote) + "</div>")
            continue

        paragraph.append(stripped)
        i += 1

    flush_paragraph()
    return mark_safe("".join(out))
