from django.shortcuts import get_object_or_404
from django.views.generic import TemplateView
from django.shortcuts import redirect, render
from django.views import View
from django.contrib import messages

from .forms import ProductForm, ProductPricingForm, CompanyForm
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.generics import ListAPIView
from django.contrib.auth.mixins import LoginRequiredMixin
from .models import Product, ProductPriceHistory, Product, Company
from .serializers import (
    PublicProductScanSerializer,
    ProductPriceHistorySerializer
)

from .services.pricing_service import update_product_pricing
from django.http import FileResponse, Http404
from django.http import FileResponse
from .services.qr_label_pdf import generate_qr_labels_pdf


class CompanyOwnerRequiredMixin(LoginRequiredMixin):
    """Réserve la vue au propriétaire d'une entreprise (rôle Formateur métier).
    Un utilisateur connecté sans Company (Apprenant/Acheteur) est redirigé
    proprement au lieu de faire planter la vue sur Company.DoesNotExist."""

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return super().dispatch(request, *args, **kwargs)
        if not Company.objects.filter(user=request.user).exists():
            messages.error(request, "Cette fonctionnalité est réservée aux comptes Formateur avec une entreprise de traçabilité.")
            return redirect("menu_page")
        return super().dispatch(request, *args, **kwargs)


class CompanySettingsView(LoginRequiredMixin, View):
    template_name = "product_transparency/company_settings.html"

    def get(self, request):
        company = get_object_or_404(Company, user=request.user)
        form = CompanyForm(instance=company)
        return render(request, self.template_name, {"form": form, "company": company})

    def post(self, request):
        company = get_object_or_404(Company, user=request.user)
        form = CompanyForm(request.POST, request.FILES, instance=company)  # ✅ FILES pour logo
        if form.is_valid():
            form.save()
            return redirect("product_transparency:company-dashboard")
        return render(request, self.template_name, {"form": form, "company": company})

# =========================
# 1️⃣ API PUBLIQUE – SCAN CLIENT
# =========================
class PublicProductScanAPIView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request, uuid):
        product = get_object_or_404(Product, uuid=uuid, company__is_active=True)

        serializer = PublicProductScanSerializer(
            product,
            context={"request": request}  # ✅ IMPORTANT (urls images)
        )
        return Response(serializer.data, status=status.HTTP_200_OK)



# =========================
# 2️⃣ PAGE HTML – SCAN CLIENT
# =========================
class ProductScanPageView(TemplateView):
    template_name = "product_transparency/scan_product.html"


# =========================
# 3️⃣ API PRIVÉE – HISTORIQUE DES PRIX
# =========================
class ProductPriceHistoryAPIView(ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ProductPriceHistorySerializer

    def get_queryset(self):
        product_id = self.kwargs["product_id"]
        return ProductPriceHistory.objects.filter(
            product_id=product_id
        ).order_by("-changed_at")



class CompanyDashboardView(CompanyOwnerRequiredMixin, TemplateView):
    template_name = "product_transparency/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        company = self.request.user.company
        context["products"] = Product.objects.filter(company=company)

        return context




class UpdateProductPricingAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, product_id):
        product = get_object_or_404(
            Product,
            id=product_id,
            company=request.user.company
        )

        update_product_pricing(
            product=product,
            price=request.data["price"],
            production_date=request.data["production_date"],
            expiry_date=request.data["expiry_date"],
            user=request.user,
            reason=request.data.get("reason", "Mise à jour manuelle")
        )

        return Response(
            {"status": "updated"},
            status=status.HTTP_200_OK
        )



class ProductCreateView(LoginRequiredMixin, View):
    template_name = "product_transparency/product_form.html"

    def get(self, request):
        form = ProductForm()
        return render(request, self.template_name, {"form": form})

    def post(self, request):
        form = ProductForm(request.POST, request.FILES)
        if form.is_valid():
            product = form.save(commit=False)
            product.company = request.user.company
            product.save()
            return redirect("product_transparency:company-dashboard")

        return render(request, self.template_name, {"form": form})



class ProductUpdateView(LoginRequiredMixin, View):
    template_name = "product_transparency/product_form.html"

    def get(self, request, product_id):
        product = get_object_or_404(
            Product,
            id=product_id,
            company=request.user.company
        )
        form = ProductForm(instance=product)
        return render(request, self.template_name, {"form": form})

    def post(self, request, product_id):
        product = get_object_or_404(
            Product,
            id=product_id,
            company=request.user.company
        )
        form = ProductForm(request.POST, request.FILES, instance=product)
        if form.is_valid():
            form.save()
            return redirect("product_transparency:company-dashboard")

        return render(request, self.template_name, {"form": form})




class ProductPricingCreateOrUpdateView(LoginRequiredMixin, View):
    template_name = "product_transparency/pricing_form.html"

    def get(self, request, product_id):
        product = get_object_or_404(Product, id=product_id, company=request.user.company)

        # Si pricing existe, on pré-remplit le ModelForm
        instance = getattr(product, "pricing", None)
        form = ProductPricingForm(instance=instance)

        return render(request, self.template_name, {"form": form, "product": product})

    def post(self, request, product_id):
        product = get_object_or_404(Product, id=product_id, company=request.user.company)

        # On valide avec le ModelForm (comme ProductForm)
        instance = getattr(product, "pricing", None)
        form = ProductPricingForm(request.POST, instance=instance)

        if form.is_valid():
            cd = form.cleaned_data

            # ✅ IMPORTANT : on n'utilise pas form.save() (sinon pas d'historique)
            update_product_pricing(
                product=product,
                price=cd["price"],
                production_date=cd["production_date"],
                expiry_date=cd["expiry_date"],
                user=request.user,
                reason=cd.get("reason", "")
            )

            return redirect("product_transparency:company-dashboard")

        return render(request, self.template_name, {"form": form, "product": product})





class DownloadProductQRView(LoginRequiredMixin, View):
    def get(self, request, product_id):
        product = Product.objects.filter(
            id=product_id,
            company=request.user.company
        ).select_related("qr").first()

        if not product or not hasattr(product, "qr") or not product.qr.qr_code:
            raise Http404("QR code introuvable")

        qr_file = product.qr.qr_code

        response = FileResponse(
            qr_file.open("rb"),
            as_attachment=True,
            filename=f"{product.sku}_QR.png"
        )
        return response


# product_transparency/views.py


class QRLabelPDFView(LoginRequiredMixin, View):

    def get(self, request):
        per_page = int(request.GET.get("per_page", 12))

        products = Product.objects.filter(
            company=request.user.company,
            qr__isnull=False
        ).select_related("company", "qr")

        # 🔥 DUPLICATION x4
        products = list(products) * 1

        pdf_buffer = generate_qr_labels_pdf(products, per_page)

        return FileResponse(
            pdf_buffer,
            as_attachment=True,
            filename="qr_labels_x4.pdf",
            content_type="application/pdf"
        )


# views.py
class ScanCartView(CompanyOwnerRequiredMixin, TemplateView):
    template_name = "product_transparency/scan_cart.html"
