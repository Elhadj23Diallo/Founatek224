from product_transparency.models import ProductPricing, ProductPriceHistory

def update_product_pricing(
    *,
    product,
    price,
    production_date,
    expiry_date,
    user=None,
    reason=""
):
    # Historique
    if hasattr(product, "pricing"):
        ProductPriceHistory.objects.create(
            product=product,
            price=product.pricing.price,
            production_date=product.pricing.production_date,
            expiry_date=product.pricing.expiry_date,
            changed_by=user,
            reason=reason
        )

    # Mise à jour
    pricing, _ = ProductPricing.objects.update_or_create(
        product=product,
        defaults={
            "price": price,
            "production_date": production_date,
            "expiry_date": expiry_date
        }
    )
    return pricing
