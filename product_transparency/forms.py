from django import forms
from .models import Product, ProductPricing, Company


class CompanyForm(forms.ModelForm):
    class Meta:
        model = Company
        fields = ["name", "slug", "logo", "currency"]


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ["name", "sku", "image", "stock"]




class ProductPricingForm(forms.ModelForm):
    reason = forms.CharField(required=False)

    class Meta:
        model = ProductPricing
        fields = ["price", "production_date", "expiry_date"]
        widgets = {
            "production_date": forms.DateInput(attrs={"type": "date"}),
            "expiry_date": forms.DateInput(attrs={"type": "date"}),
        }

