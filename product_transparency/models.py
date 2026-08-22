from django.db import models
import uuid
from django.conf import settings
# product_transparency/models.py



# product_transparency/models.py
from django.db import models

class Company(models.Model):
    CURRENCY_CHOICES = [
        ("GNF", "Franc guinéen (GNF)"),
        ("XOF", "Franc CFA (XOF)"),
        ("USD", "Dollar américain (USD)"),
        ("EUR", "Euro (EUR)"),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="company",
        blank=True,
        null=True
    )

    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)

    logo = models.ImageField(
        upload_to="company_logos/",
        blank=True,
        null=True
    )

    currency = models.CharField(
        max_length=3,
        choices=CURRENCY_CHOICES,
        default="GNF"
    )

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name




import uuid
from django.db import models
from product_transparency.services.qr_service import generate_qr_for_product



class Product(models.Model):
    company = models.ForeignKey(
        "Company",
        on_delete=models.CASCADE,
        related_name="products"
    )
    name = models.CharField(max_length=255)
    sku = models.CharField(max_length=100, unique=True)

    image = models.ImageField(
        upload_to="product_images/",
        blank=True,
        null=True
    )

    uuid = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True
    )

    stock = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Quantité en stock. Laisser vide pour ne pas suivre le stock (vente illimitée)."
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.sku})"

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)

        # Générer le QR UNIQUEMENT à la création
        if is_new:
            generate_qr_for_product(self)





class ProductPricing(models.Model):
    product = models.OneToOneField(
        Product,
        on_delete=models.CASCADE,
        related_name="pricing"
    )

    price = models.DecimalField(max_digits=10, decimal_places=2)

    production_date = models.DateField()
    expiry_date = models.DateField()

    updated_at = models.DateTimeField(auto_now=True)

    def is_expired(self):
        from django.utils.timezone import now
        return self.expiry_date < now().date()

    def __str__(self):
        return f"{self.product.name} - {self.price}"


class ProductQR(models.Model):
    product = models.OneToOneField(
        Product,
        on_delete=models.CASCADE,
        related_name="qr"
    )

    qr_code = models.ImageField(upload_to="qr_codes/", blank=True)
    qr_hash = models.CharField(max_length=255, unique=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"QR - {self.product.name}"



class ProductPriceHistory(models.Model):
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="price_history"
    )

    price = models.DecimalField(max_digits=10, decimal_places=2)
    production_date = models.DateField()
    expiry_date = models.DateField()

    changed_at = models.DateTimeField(auto_now_add=True)

    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    reason = models.CharField(
        max_length=255,
        blank=True,
        help_text="Ex: Mise à jour prix, correction date, promo"
    )

    def __str__(self):
        return f"{self.product.name} - {self.price} @ {self.changed_at}"




class Sale(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey("Company", on_delete=models.CASCADE)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Sale {self.id} - {self.total_amount}"


class SaleItem(models.Model):
    sale = models.ForeignKey(Sale, related_name="items", on_delete=models.CASCADE)
    product = models.ForeignKey("Product", on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)

    def line_total(self):
        return self.quantity * self.unit_price
