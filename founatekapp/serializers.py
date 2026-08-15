from rest_framework import serializers
from django.contrib.auth.models import User
from .models import Category, Product, ProductImage, Order, OrderItem, Cart, CartItem, Review, LoyaltyAccount, LoyaltyTransaction


class ReviewSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = Review
        fields = ['id', 'username', 'rating', 'comment', 'created_at']
        read_only_fields = ['id', 'username', 'created_at']


class CategorySerializer(serializers.ModelSerializer):
    product_count = serializers.IntegerField(source='products.count', read_only=True)
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ['id', 'name', 'slug', 'description', 'image_url', 'product_count']

    def get_image_url(self, obj):
        request = self.context.get('request')
        if obj.image and request:
            return request.build_absolute_uri(obj.image.url)
        return None


class ProductImageSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = ProductImage
        fields = ['id', 'image_url', 'alt', 'order']

    def get_image_url(self, obj):
        request = self.context.get('request')
        if obj.image and request:
            return request.build_absolute_uri(obj.image.url)
        return None


class ProductListSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    category_slug = serializers.CharField(source='category.slug', read_only=True)
    main_image_url = serializers.SerializerMethodField()
    in_stock = serializers.BooleanField(read_only=True)
    average_rating = serializers.FloatField(read_only=True)
    review_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Product
        fields = [
            'id', 'name', 'slug', 'category_name', 'category_slug',
            'price', 'stock', 'in_stock', 'main_image_url',
            'average_rating', 'review_count',
        ]

    def get_main_image_url(self, obj):
        request = self.context.get('request')
        if obj.image and request:
            return request.build_absolute_uri(obj.image.url)
        return None


class ProductDetailSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)
    gallery = ProductImageSerializer(many=True, read_only=True)
    all_images = serializers.SerializerMethodField()
    in_stock = serializers.BooleanField(read_only=True)
    average_rating = serializers.FloatField(read_only=True)
    review_count = serializers.IntegerField(read_only=True)
    reviews = ReviewSerializer(many=True, read_only=True)

    class Meta:
        model = Product
        fields = [
            'id', 'name', 'slug', 'category', 'description', 'specifications',
            'price', 'stock', 'in_stock', 'all_images', 'gallery',
            'average_rating', 'review_count', 'reviews',
            'created_at', 'updated_at',
        ]

    def get_all_images(self, obj):
        request = self.context.get('request')
        images = []
        if obj.image and request:
            images.append(request.build_absolute_uri(obj.image.url))
        for img in obj.gallery.order_by('order'):
            if request:
                images.append(request.build_absolute_uri(img.image.url))
        return images


class OrderItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_slug = serializers.CharField(source='product.slug', read_only=True)
    subtotal = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = OrderItem
        fields = ['id', 'product_name', 'product_slug', 'quantity', 'unit_price', 'subtotal']


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    subtotal = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    total = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    total_items = serializers.IntegerField(read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    payment_method_display = serializers.CharField(source='get_payment_method_display', read_only=True)
    payment_status_display = serializers.CharField(source='get_payment_status_display', read_only=True)

    class Meta:
        model = Order
        fields = [
            'id', 'status', 'status_display', 'shipping_address', 'phone', 'contact_email', 'note',
            'payment_method', 'payment_method_display', 'payment_status', 'payment_status_display',
            'payment_reference', 'discount', 'subtotal', 'total', 'total_items', 'items',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['status', 'payment_status', 'discount', 'created_at', 'updated_at']


class LoyaltyTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = LoyaltyTransaction
        fields = ['id', 'points', 'kind', 'description', 'created_at']


class LoyaltyAccountSerializer(serializers.ModelSerializer):
    discount_value = serializers.IntegerField(read_only=True)
    next_level_info = serializers.SerializerMethodField()
    level_display = serializers.CharField(source='get_level_display', read_only=True)
    transactions = serializers.SerializerMethodField()

    class Meta:
        model = LoyaltyAccount
        fields = [
            'points', 'total_spent', 'level', 'level_display',
            'discount_value', 'next_level_info', 'transactions',
        ]

    def get_next_level_info(self, obj):
        return obj.next_level_info

    def get_transactions(self, obj):
        return LoyaltyTransactionSerializer(obj.transactions.all()[:20], many=True).data


class CartItemSerializer(serializers.ModelSerializer):
    product = ProductListSerializer(read_only=True)
    product_id = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.filter(is_active=True),
        source='product', write_only=True
    )
    subtotal = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = CartItem
        fields = ['id', 'product', 'product_id', 'quantity', 'subtotal']


class CartSerializer(serializers.ModelSerializer):
    cart_items = CartItemSerializer(many=True, read_only=True)
    total = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    total_items = serializers.IntegerField(read_only=True)

    class Meta:
        model = Cart
        fields = ['id', 'cart_items', 'total', 'total_items']


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=6)
    password2 = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ['username', 'email', 'password', 'password2']

    def validate(self, data):
        if data['password'] != data['password2']:
            raise serializers.ValidationError({'password2': 'Les mots de passe ne correspondent pas.'})
        return data

    def create(self, validated_data):
        validated_data.pop('password2')
        user = User.objects.create_user(**validated_data)
        return user

