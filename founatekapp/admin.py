from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from .models import Category, Product, ProductImage, Order, OrderItem, Cart, CartItem, LoyaltyAccount, LoyaltyTransaction, ExchangeRate, Review


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug']
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ['name']


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1
    fields = ['image', 'alt', 'order']


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ['unit_price', 'subtotal']


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'price', 'stock', 'is_active']
    list_filter = ['category', 'is_active']
    list_editable = ['price', 'stock', 'is_active']
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ['name', 'description']
    inlines = [ProductImageInline]
    actions = ['valider_produits']

    def valider_produits(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f"{updated} produit(s) valide(s) et publie(s) sur la boutique.")
    valider_produits.short_description = 'Valider les produits selectionnes'


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'status', 'payment_status', 'payment_method', 'total', 'created_at']
    list_filter = ['status', 'payment_status', 'payment_method']
    search_fields = ['user__username', 'shipping_address']
    inlines = [OrderItemInline]
    readonly_fields = ['created_at', 'updated_at']
    list_display = ['id', 'user', 'status', 'payment_status', 'payment_method', 'total', 'created_at', 'recu_pdf']

    def recu_pdf(self, obj):
        url = reverse('founatekapp:order_receipt', args=[obj.pk])
        return format_html('<a href="{}" target="_blank">Telecharger le recu</a>', url)
    recu_pdf.short_description = 'Recu'


class CartItemInline(admin.TabularInline):
    model = CartItem
    extra = 0


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ['user', 'total_items', 'total']
    inlines = [CartItemInline]


class LoyaltyTransactionInline(admin.TabularInline):
    model = LoyaltyTransaction
    extra = 0
    readonly_fields = ['points', 'kind', 'description', 'order', 'created_at']


@admin.register(ExchangeRate)
class ExchangeRateAdmin(admin.ModelAdmin):
    list_display = ['currency_code', 'currency_symbol', 'rate_from_gnf', 'updated_at']
    search_fields = ['currency_code']


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ['product', 'user', 'rating', 'created_at']
    list_filter = ['rating']
    search_fields = ['product__name', 'user__username', 'comment']


@admin.register(LoyaltyAccount)
class LoyaltyAccountAdmin(admin.ModelAdmin):
    list_display = ['user', 'points', 'level', 'total_spent', 'discount_value']
    list_filter = ['level']
    search_fields = ['user__username']
    readonly_fields = ['total_spent', 'updated_at', 'created_at']
    inlines = [LoyaltyTransactionInline]

