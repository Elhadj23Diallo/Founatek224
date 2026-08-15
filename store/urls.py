from django.urls import path
from . import views

app_name = 'store'

urlpatterns = [
    path('', views.home, name='home'),
    path('produits/', views.product_list, name='product_list'),
    path('categorie/<slug:slug>/', views.category_detail, name='category'),
    path('produit/<slug:slug>/', views.product_detail, name='product_detail'),
    path('panier/', views.cart_detail, name='cart'),
    path('panier/ajouter/<int:product_id>/', views.cart_add, name='cart_add'),
    path('panier/retirer/<int:item_id>/', views.cart_remove, name='cart_remove'),
    path('panier/modifier/<int:item_id>/', views.cart_update, name='cart_update'),
    path('commander/', views.checkout, name='checkout'),
    path('commandes/', views.order_list, name='order_list'),
    path('commandes/<int:pk>/confirmation/', views.order_confirmation, name='order_confirmation'),
    path('commandes/<int:pk>/', views.order_detail, name='order_detail'),
    path('commandes/<int:pk>/recu/', views.order_receipt_pdf, name='order_receipt'),
    path('fidelite/', views.loyalty_dashboard, name='loyalty'),
]
