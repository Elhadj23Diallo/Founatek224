from django.contrib import admin
from .models import (
    Company,
    Product,
    ProductPricing,
    ProductQR,
    ProductPriceHistory, Sale, SaleItem
)


# =========================
# COMPANY
# =========================
@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ("name", "user", "is_active", "created_at")
    search_fields = ("name", "slug")
    list_filter = ("is_active",)
    prepopulated_fields = {"slug": ("name",)}


# =========================
# PRODUCT
# =========================
@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "sku", "company", "created_at")
    search_fields = ("name", "sku")
    list_filter = ("company",)
    readonly_fields = ("uuid",)


# =========================
# PRODUCT PRICING
# =========================
@admin.register(ProductPricing)
class ProductPricingAdmin(admin.ModelAdmin):
    list_display = (
        "product",
        "price",
        "production_date",
        "expiry_date",
        "updated_at",
    )
    list_filter = ("expiry_date",)
    search_fields = ("product__name", "product__sku")


# =========================
# PRODUCT QR
# =========================
@admin.register(ProductQR)
class ProductQRAdmin(admin.ModelAdmin):
    list_display = ("product", "created_at")
    readonly_fields = ("qr_code", "qr_hash")




# product_transparency/admin.py
from django.contrib import admin
from .models import Sale, SaleItem


class SaleItemInline(admin.TabularInline):
    model = SaleItem
    extra = 0


@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = ("id", "company", "total_amount", "created_at")
    list_filter = ("company", "created_at")
    inlines = [SaleItemInline]


@admin.register(SaleItem)
class SaleItemAdmin(admin.ModelAdmin):
    list_display = ("sale", "product", "quantity", "unit_price")

