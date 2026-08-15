from django.urls import path
from .views import (
    PublicProductScanAPIView,
    ProductScanPageView,
    ProductPriceHistoryAPIView, CompanyDashboardView, UpdateProductPricingAPIView, ProductCreateView, ProductUpdateView, ProductPricingCreateOrUpdateView, CompanySettingsView, DownloadProductQRView, QRLabelPDFView, ScanCartView
)

from product_transparency.api.sales import CreateSaleAPIView, SaleTicketPDFView

app_name = "product_transparency"

urlpatterns = [
    # Scan public
    path(
        "api/public/products/<uuid:uuid>/",
        PublicProductScanAPIView.as_view(),
        name="public-product-scan"
    ),

    # Page HTML scan
    path(
        "p/<uuid:uuid>/",
        ProductScanPageView.as_view(),
        name="product-scan-page"
    ),

    # Historique des prix (privé)
    path(
        "api/products/<int:product_id>/price-history/",
        ProductPriceHistoryAPIView.as_view(),
        name="product-price-history"
    ),

    path(
    "dashboard/",
    CompanyDashboardView.as_view(),
    name="company-dashboard"
    ),

    path(
    "api/products/<int:product_id>/update-pricing/",
    UpdateProductPricingAPIView.as_view(),
    name="update-product-pricing"
    ),

    path(
    "dashboard/products/add/",
    ProductCreateView.as_view(),
    name="product-add"
    ),

    path(
        "dashboard/products/<int:product_id>/edit/",
        ProductUpdateView.as_view(),
        name="product-edit"
    ),

    path(
    "dashboard/products/<int:product_id>/pricing/",
    ProductPricingCreateOrUpdateView.as_view(),
    name="product-pricing"
    ),
    path("dashboard/settings/", CompanySettingsView.as_view(), name="company-settings"),
    path(
    "dashboard/products/<int:product_id>/qr/download/",
    DownloadProductQRView.as_view(),
    name="product-qr-download"
    ),
    # product_transparency/urls.py

    path(
        "dashboard/qr-labels/pdf/",
        QRLabelPDFView.as_view(),
        name="qr-labels-pdf"
    ),
    path("scan-cart/", ScanCartView.as_view(), name="scan-cart"),
    path("api/sales/", CreateSaleAPIView.as_view(), name="create-sale"),
        path(
        "api/sales/<uuid:sale_id>/pdf/",
        SaleTicketPDFView.as_view(),
        name="sale-ticket-pdf"
    ),
]
