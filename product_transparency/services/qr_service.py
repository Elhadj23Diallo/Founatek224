import qrcode
import hashlib
from io import BytesIO
from PIL import Image
from django.core.files import File
from django.conf import settings


def generate_qr_for_product(product):
    from product_transparency.models import ProductQR

    public_url = (
        f"{settings.SITE_URL}"
        f"/product_transparency/p/{product.uuid}/"
    )

    qr_hash = hashlib.sha256(
        f"{product.uuid}:{product.sku}:{product.company_id}".encode()
    ).hexdigest()

    # 🔥 QR haute qualité
    qr = qrcode.QRCode(
        version=6,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=4,
    )
    qr.add_data(public_url)
    qr.make(fit=True)

    qr_img = qr.make_image(fill_color="black", back_color="white").convert("RGB")

    # 🔥 LOGO AU CENTRE
    if product.company.logo:
        logo = Image.open(product.company.logo.path).convert("RGBA")

        qr_width, qr_height = qr_img.size
        logo_size = qr_width // 4  # 25%
        logo = logo.resize((logo_size, logo_size), Image.LANCZOS)

        # fond blanc sous logo
        bg = Image.new("RGBA", (logo_size + 20, logo_size + 20), "WHITE")
        pos = ((qr_width - bg.size[0]) // 2, (qr_height - bg.size[1]) // 2)
        qr_img.paste(bg, pos)

        logo_pos = (
            (qr_width - logo_size) // 2,
            (qr_height - logo_size) // 2,
        )
        qr_img.paste(logo, logo_pos, mask=logo)

    buffer = BytesIO()
    qr_img.save(buffer, format="PNG")
    buffer.seek(0)

    product_qr, _ = ProductQR.objects.update_or_create(
        product=product,
        defaults={"qr_hash": qr_hash}
    )

    product_qr.qr_code.save(
        f"{product.sku}_{product.uuid}.png",
        File(buffer),
        save=True
    )

    return product_qr
