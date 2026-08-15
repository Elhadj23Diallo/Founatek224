from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
from django.conf import settings


def generate_qr_label(product):
    qr_img = Image.open(product.qr.qr_code.path).convert("RGB")

    width = 500
    height = 650
    canvas = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(canvas)

    # QR
    qr_size = 380
    qr_img = qr_img.resize((qr_size, qr_size), Image.LANCZOS)
    canvas.paste(qr_img, ((width - qr_size) // 2, 20))

    # Fonts
    font_title = ImageFont.truetype(
        settings.BASE_DIR / "static/fonts/Orbitron-Bold.ttf", 26
    )
    font_text = ImageFont.truetype(
        settings.BASE_DIR / "static/fonts/Roboto-Regular.ttf", 20
    )

    y = 420
    draw.text((width // 2, y), product.name, fill="black", font=font_title, anchor="mm")
    y += 40

    draw.text((width // 2, y),
              f"{product.pricing.price} {product.company.currency}",
              fill="black", font=font_text, anchor="mm")
    y += 30

    draw.text((width // 2, y),
              f"Prod: {product.pricing.production_date}",
              fill="black", font=font_text, anchor="mm")
    y += 25

    draw.text((width // 2, y),
              f"Exp: {product.pricing.expiry_date}",
              fill="black", font=font_text, anchor="mm")
    y += 25

    draw.text((width // 2, y),
              f"UID: {product.uuid}",
              fill="gray", font=font_text, anchor="mm")

    buffer = BytesIO()
    canvas.save(buffer, format="PNG")
    buffer.seek(0)

    return buffer
