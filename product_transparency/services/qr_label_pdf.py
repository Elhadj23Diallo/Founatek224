import os
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor
from reportlab.platypus import Paragraph, Frame, KeepInFrame
from reportlab.lib.styles import ParagraphStyle

# ================== COULEURS ==================
CHARCOAL = HexColor("#2c3e50")
SLATE = HexColor("#7f8c8d")
ACCENT_BLUE = HexColor("#1abc9c")
BORDER_GREY = HexColor("#dddddd")
PRICE_BG = HexColor("#e8f8f5")

# ================== STYLES TEXTE ==================
STYLES = {
    "company": ParagraphStyle(
        "company",
        fontName="Helvetica-Bold",
        fontSize=5,  # légèrement plus petit
        leading=6,
        textColor=CHARCOAL,
        spaceAfter=1,
    ),
    "product": ParagraphStyle(
        "product",
        fontName="Helvetica-Bold",
        fontSize=7,  # légèrement plus petit
        leading=8,
        textColor=CHARCOAL,
        spaceAfter=1,
    ),
    "price": ParagraphStyle(
        "price",
        fontName="Helvetica-Bold",
        fontSize=7,
        leading=8,
        textColor=ACCENT_BLUE,
        backColor=PRICE_BG,
        borderPadding=1,
        spaceAfter=1,
    ),
    "meta": ParagraphStyle(
        "meta",
        fontName="Helvetica",
        fontSize=4,
        leading=5,
        textColor=SLATE,
        spaceAfter=1,
    ),
    "uid": ParagraphStyle(
        "uid",
        fontName="Helvetica",
        fontSize=4,
        leading=5,
        textColor=SLATE,
        spaceBefore=1,
    ),
}

# ================== UTILS ==================
def safe_path(field):
    if field and hasattr(field, "path") and os.path.exists(field.path):
        return field.path
    return None

# ================== PDF GENERATOR ==================
def generate_qr_labels_pdf(products, per_page=12):
    """
    Génère un PDF avec des étiquettes 50x30mm pour NIIMBOT B1
    """
    buffer = BytesIO()
    from reportlab.lib.pagesizes import A4
    c = canvas.Canvas(buffer, pagesize=A4)
    page_width, page_height = A4

    # ----- GRILLE -----
    LABEL_W = 50 * mm
    LABEL_H = 30 * mm

    GAP_X = 2 * mm
    GAP_Y = 2 * mm
    MARGIN_X = 5 * mm
    MARGIN_Y = 5 * mm

    cols = int((page_width - 2 * MARGIN_X + GAP_X) // (LABEL_W + GAP_X))
    rows = int((page_height - 2 * MARGIN_Y + GAP_Y) // (LABEL_H + GAP_Y))

    for i, product in enumerate(products):
        if i > 0 and i % (cols * rows) == 0:
            c.showPage()

        col = i % cols
        row = rows - 1 - ((i // cols) % rows)

        x = MARGIN_X + col * (LABEL_W + GAP_X)
        y = MARGIN_Y + row * (LABEL_H + GAP_Y)

        # ===== CADRE =====
        c.setStrokeColor(BORDER_GREY)
        c.setLineWidth(0.5)
        c.rect(x, y, LABEL_W, LABEL_H, stroke=1, fill=0)

        pad = 2 * mm
        ix, iy = x + pad, y + pad
        iw, ih = LABEL_W - 2 * pad, LABEL_H - 2 * pad

        # ================= HEADER (Company) =================
        header_h = 5 * mm
        logo_path = safe_path(product.company.logo)
        if logo_path:
            c.drawImage(
                logo_path,
                ix,
                iy + ih - header_h,
                width=8 * mm,
                height=4 * mm,
                preserveAspectRatio=True,
                mask="auto"
            )

        header_frame = Frame(
            ix + 10 * mm,
            iy + ih - header_h,
            iw - 10 * mm,
            header_h,
            showBoundary=0
        )
        # ajout du nom de l'entreprise dans le texte
        header_frame.addFromList([Paragraph(product.company.name, STYLES["company"])], c)

        # ================= QR CODE =================
        QR_SIZE = 8 * mm  # plus petit
        qr_path = safe_path(product.qr.qr_code if product.qr else None)
        if qr_path:
            c.drawImage(
                qr_path,
                ix + iw - QR_SIZE,
                iy + ih - QR_SIZE - 1 * mm,
                width=QR_SIZE,
                height=QR_SIZE,
                preserveAspectRatio=True,
                mask="auto"
            )

        # ================= TEXTE PRODUIT =================
        text_frame = Frame(
            ix,
            iy,
            iw,
            ih - header_h - 1 * mm,
            showBoundary=0
        )

        story = [
            Paragraph(product.company.name, STYLES["company"]),  # nom de l'entreprise ajouté
            Paragraph(product.name, STYLES["product"])
        ]

        if hasattr(product, "pricing"):
            story.append(Paragraph(f"{product.pricing.price} {product.company.currency}", STYLES["price"]))
            story.append(Paragraph(f"Prod: {product.pricing.production_date.strftime('%d/%m/%Y')}", STYLES["meta"]))
            story.append(Paragraph(f"Exp: {product.pricing.expiry_date.strftime('%d/%m/%Y')}", STYLES["meta"]))

        story.append(Paragraph(f"UID: {product.uuid}", STYLES["uid"]))

        text_frame.addFromList([KeepInFrame(iw, ih - header_h, story, mode="shrink")], c)

    c.save()
    buffer.seek(0)
    return buffer
