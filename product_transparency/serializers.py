from rest_framework import serializers
from .models import Product, ProductPriceHistory

class PublicProductScanSerializer(serializers.ModelSerializer):
    price = serializers.SerializerMethodField()
    production_date = serializers.SerializerMethodField()
    expiry_date = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()

    company = serializers.CharField(source="company.name", read_only=True)
    currency = serializers.CharField(source="company.currency", read_only=True)  # ✅ NEW

    uid = serializers.UUIDField(source="uuid", read_only=True)  # ✅ NEW (si tu veux afficher UID)
    image = serializers.SerializerMethodField()
    company_logo = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            "name",
            "company",
            "currency",
            "uid",
            "price",
            "production_date",
            "expiry_date",
            "status",
            "image",
            "company_logo",
        ]

    def get_price(self, obj):
        return obj.pricing.price if hasattr(obj, "pricing") else None

    def get_production_date(self, obj):
        return obj.pricing.production_date if hasattr(obj, "pricing") else None

    def get_expiry_date(self, obj):
        return obj.pricing.expiry_date if hasattr(obj, "pricing") else None

    def get_status(self, obj):
        if not hasattr(obj, "pricing"):
            return "INCONNU"
        return "EXPIRÉ" if obj.pricing.is_expired() else "VALIDE"

    def get_image(self, obj):
        if obj.image:
            request = self.context.get("request")
            return request.build_absolute_uri(obj.image.url) if request else obj.image.url
        return None

    def get_company_logo(self, obj):
        if obj.company.logo:
            request = self.context.get("request")
            return request.build_absolute_uri(obj.company.logo.url) if request else obj.company.logo.url
        return None


class ProductPriceHistorySerializer(serializers.ModelSerializer):
    changed_by = serializers.CharField(source="changed_by.username", default=None)

    class Meta:
        model = ProductPriceHistory
        fields = ["price", "production_date", "expiry_date", "changed_at", "changed_by", "reason"]
