import os
from datetime import date
from django.conf import settings
from django.utils import timezone
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor
from reportlab.lib.units import cm
from reportlab.lib.utils import ImageReader

print("🔥 PDF FILE LOADED :", __file__)

# ==============================
# 📅 Mois en français
# ==============================
MOIS_FR = [
    "", "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre"
]


def darken_hex(hex_color, factor=0.75):
    hex_color = hex_color.lstrip("#")
    r, g, b = (
        int(hex_color[0:2], 16),
        int(hex_color[2:4], 16),
        int(hex_color[4:6], 16),
    )
    return f"#{int(r*factor):02x}{int(g*factor):02x}{int(b*factor):02x}"


def generer_certificat_pdf(certification):
    user = certification.user
    parcours = certification.parcours
    organisation = parcours.organisation
    score = certification.score_final

    # ==============================
    # 🎨 COULEURS DYNAMIQUES
    # ==============================
    base_color = organisation.couleur_principale or "#050a1f"

    COL_DARK_BG = HexColor(darken_hex(base_color))
    COL_ACCENT_1 = HexColor(base_color)
    COL_ACCENT_2 = HexColor("#00ff99")
    COL_TEXT_MAIN = HexColor("#1a243d")
    COL_TEXT_LIGHT = HexColor("#ffffff")
    COL_GREY = HexColor("#8892b0")

    # ==============================
    # 📄 FICHIER
    # ==============================
    filename = (
        f"certificat_{user.username}_{certification.uuid}_"
        f"{int(timezone.now().timestamp())}.pdf"
    )
    relative_path = f"certificats/{filename}"
    filepath = os.path.join(settings.MEDIA_ROOT, relative_path)
    os.makedirs(os.path.dirname(filepath), exist_ok=True)

    c = canvas.Canvas(filepath, pagesize=landscape(A4))
    width, height = landscape(A4)

    # ==============================
    # 🖌️ BANDE GAUCHE
    # ==============================
    band_width = width * 0.25

    path = c.beginPath()
    path.moveTo(0, 0)
    path.lineTo(band_width, 0)
    path.lineTo(width * 0.10, height)
    path.lineTo(0, height)
    path.close()

    c.setFillColor(COL_DARK_BG)
    c.drawPath(path, fill=1, stroke=0)

    c.setStrokeColor(COL_ACCENT_1)
    c.setLineWidth(4)
    c.line(band_width, 0, width * 0.10, height)

    # ==============================
    # 🖼️ LOGO — ENCORE PLUS HAUT & À DROITE (ROND)
    # ==============================
    logo_reader = None

    if organisation.logo and os.path.exists(organisation.logo.path):
        logo_reader = ImageReader(organisation.logo.path)
    else:
        fallback = os.path.join(
            settings.BASE_DIR, "static", "iot", "logo_founatek.png"
        )
        if os.path.exists(fallback):
            logo_reader = ImageReader(fallback)

    if logo_reader:
        radius = 1.7 * cm

        # 🔥 encore plus haut & droite
        cx = width - 0.6 * cm - radius
        cy = height - 0.6 * cm - radius

        c.setFillColor(COL_DARK_BG)
        c.circle(cx, cy, radius, fill=1, stroke=0)

        c.saveState()
        p = c.beginPath()
        p.circle(cx, cy, radius)
        c.clipPath(p, stroke=0)

        c.drawImage(
            logo_reader,
            cx - radius,
            cy - radius,
            width=2 * radius,
            height=2 * radius,
            preserveAspectRatio=True,
            mask="auto"
        )
        c.restoreState()

        c.setStrokeColor(COL_ACCENT_1)
        c.setLineWidth(2)
        c.circle(cx, cy, radius, fill=0)

    # ==============================
    # 🏷️ NOM ORGANISATION
    # ==============================
    c.setFont("Times-Bold", 10)
    c.setFillColor(COL_ACCENT_1)
    c.drawString(
        1.1 * cm,
        height / 2 + 2 * cm,
        organisation.nom.upper()
    )

    # ==============================
    # 🏆 CONTENU CENTRAL
    # ==============================
    center_x = width * 0.60

    c.setFont("Times-Bold", 13)
    c.setFillColor(COL_GREY)
    c.drawCentredString(
        center_x,
        height - 4 * cm,
        f"{organisation.nom.upper()} — CERTIFICATION OFFICIELLE"
    )

    c.setFont("Times-Bold", 38)
    c.setFillColor(COL_DARK_BG)
    c.drawCentredString(
        center_x,
        height - 5.6 * cm,
        "CERTIFICAT DE RÉUSSITE"
    )

    c.setStrokeColor(COL_ACCENT_1)
    c.setLineWidth(2)
    c.line(center_x - 4.5 * cm, height - 6.2 * cm,
           center_x + 4.5 * cm, height - 6.2 * cm)

    c.setFont("Times-Roman", 15)
    c.setFillColor(COL_TEXT_MAIN)
    c.drawCentredString(center_x, height - 8.3 * cm, "Décerné officiellement à :")

    c.setFont("Times-Bold", 32)
    c.setFillColor(COL_DARK_BG)
    c.drawCentredString(
        center_x,
        height - 10 * cm,
        f"{user.first_name} {user.last_name}".upper()
    )

    c.setFont("Times-Roman", 15)
    c.drawCentredString(center_x, height - 12 * cm,
                        "Pour la validation du parcours :")

    c.setFont("Times-Bold", 23)
    c.setFillColor(COL_ACCENT_1)
    c.drawCentredString(center_x, height - 13.6 * cm, parcours.titre)

    # ==============================
    # 🧠 SCORE
    # ==============================
    badge_x = width - 3.3 * cm
    badge_y = 4.9 * cm

    c.setFillColor(COL_DARK_BG)
    c.circle(badge_x, badge_y, 2 * cm, fill=1)

    c.setStrokeColor(COL_ACCENT_2)
    c.setLineWidth(3)
    c.circle(badge_x, badge_y, 1.9 * cm)

    c.setFont("Times-Bold", 24)
    c.setFillColor(COL_ACCENT_2)
    c.drawCentredString(badge_x, badge_y - 6, f"{int(score)}%")

    c.setFont("Times-Roman", 8)
    c.setFillColor(COL_TEXT_LIGHT)
    c.drawCentredString(badge_x, badge_y - 20, "SCORE FINAL")

    # ==============================
    # 🦶 PIED DE PAGE
    # ==============================
    today = date.today()
    date_str = f"{today.day} {MOIS_FR[today.month]} {today.year}"

    c.setFont("Times-Bold", 11)
    c.setFillColor(COL_TEXT_MAIN)
    c.drawCentredString(center_x, 4.7 * cm, f"Délivré le {date_str}")

    c.setStrokeColor(COL_ACCENT_1)
    c.setLineWidth(1)
    c.line(center_x - 4 * cm, 3.7 * cm,
           center_x + 4 * cm, 3.7 * cm)

    c.setFont("Times-Italic", 11)
    c.drawCentredString(
        center_x,
        3 * cm,
        f"Certificat émis par {organisation.nom} via Founatek Academy"
    )

    c.setFont("Times-Roman", 8)
    c.setFillColor(COL_GREY)
    c.drawCentredString(
        width / 2,
        1.1 * cm,
        f"ID : {certification.uuid} — Vérifiable en ligne"
    )
    
    # ==============================
    # 🔳 QR CODE — VÉRIFICATION (BAS GAUCHE)
    # ==============================
    if certification.qr_code and os.path.exists(certification.qr_code.path):
        qr_reader = ImageReader(certification.qr_code.path)

        qr_size = 2.8 * cm

        # 👉 position DANS la bande gauche
        qr_x = 1.2 * cm
        qr_y = 1.3 * cm

        # cadre (clair sur fond foncé)
        c.setStrokeColor(COL_TEXT_LIGHT)
        c.setLineWidth(1)
        c.rect(
            qr_x - 0.2 * cm,
            qr_y - 0.2 * cm,
            qr_size + 0.4 * cm,
            qr_size + 0.4 * cm
        )

        # image QR
        c.drawImage(
            qr_reader,
            qr_x,
            qr_y,
            width=qr_size,
            height=qr_size,
            preserveAspectRatio=True,
            mask="auto"
        )

        # label
        c.setFont("Times-Bold", 7)
        c.setFillColor(COL_TEXT_LIGHT)
        c.drawCentredString(
            qr_x + qr_size / 2,
            qr_y - 0.45 * cm,
            "SCAN POUR VÉRIFIER"
        )



    # ==============================
    # 💾 SAUVEGARDE
    # ==============================
    c.showPage()
    c.save()

    return relative_path
