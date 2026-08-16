from django.urls import path
from . import api_views

urlpatterns = [
    # Auth
    path('auth/register/', api_views.api_register, name='api_register'),
    path('auth/login/', api_views.api_login, name='api_login'),
    path('auth/logout/', api_views.api_logout, name='api_logout'),
    path('auth/profile/', api_views.api_profile, name='api_profile'),

    # Catalogue
    path('categories/', api_views.CategoryListView.as_view(), name='api_categories'),
    path('categories/<slug:slug>/', api_views.api_category_detail, name='api_category_detail'),
    path('products/', api_views.ProductListView.as_view(), name='api_products'),
    path('products/<slug:slug>/', api_views.ProductDetailView.as_view(), name='api_product_detail'),

    # Panier
    path('cart/', api_views.api_cart, name='api_cart'),
    path('cart/add/', api_views.api_cart_add, name='api_cart_add'),
    path('cart/items/<int:item_id>/', api_views.api_cart_update, name='api_cart_update'),
    path('cart/items/<int:item_id>/remove/', api_views.api_cart_remove, name='api_cart_remove'),

    # Commandes
    path('orders/', api_views.api_order_list, name='api_orders'),
    path('orders/<int:pk>/', api_views.api_order_detail, name='api_order_detail'),
    path('orders/checkout/', api_views.api_checkout, name='api_checkout'),
    path('orders/<int:pk>/receipt/', api_views.api_order_receipt_pdf, name='api_order_receipt_pdf'),

    # Avis & fidélité
    path('products/<int:product_id>/review/', api_views.api_submit_review, name='api_submit_review'),
    path('loyalty/', api_views.api_loyalty, name='api_loyalty'),

    # Devises
    path('currencies/', api_views.api_currencies, name='api_currencies'),
    path('currency-preference/', api_views.api_currency_preference, name='api_currency_preference'),
]

