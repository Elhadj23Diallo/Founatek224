from rest_framework import generics, status, filters
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.authtoken.models import Token
from django.contrib.auth import authenticate
from django.db.models import Q
from django.shortcuts import get_object_or_404

from .models import Category, Product, Cart, CartItem, Order, OrderItem, Review, LoyaltyAccount
from .serializers import (
    CategorySerializer, ProductListSerializer, ProductDetailSerializer,
    CartSerializer, CartItemSerializer, OrderSerializer, RegisterSerializer,
    ReviewSerializer, LoyaltyAccountSerializer,
)


# â”€â”€ Auth â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@api_view(['POST'])
@permission_classes([AllowAny])
def api_register(request):
    serializer = RegisterSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.save()
        token, _ = Token.objects.get_or_create(user=user)
        return Response({'token': token.key, 'username': user.username}, status=201)
    return Response(serializer.errors, status=400)


@api_view(['POST'])
@permission_classes([AllowAny])
def api_login(request):
    username = request.data.get('username')
    password = request.data.get('password')
    user = authenticate(username=username, password=password)
    if user:
        token, _ = Token.objects.get_or_create(user=user)
        return Response({
            'token': token.key,
            'username': user.username,
            'email': user.email,
            'is_staff': user.is_staff,
        })
    return Response({'error': 'Identifiants invalides.'}, status=400)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_logout(request):
    request.user.auth_token.delete()
    return Response({'message': 'Déconnecté avec succès.'})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_profile(request):
    user = request.user
    return Response({
        'id': user.id,
        'username': user.username,
        'email': user.email,
        'is_staff': user.is_staff,
        'date_joined': user.date_joined,
    })


# â”€â”€ Catalogue â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class CategoryListView(generics.ListAPIView):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [AllowAny]


class ProductListView(generics.ListAPIView):
    serializer_class = ProductListSerializer
    permission_classes = [AllowAny]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'description', 'category__name']
    ordering_fields = ['price', 'name', 'created_at', 'stock']
    ordering = ['-created_at']

    def get_queryset(self):
        qs = Product.objects.filter(is_active=True)
        category = self.request.query_params.get('category')
        min_price = self.request.query_params.get('min_price')
        max_price = self.request.query_params.get('max_price')
        in_stock = self.request.query_params.get('in_stock')
        if category:
            qs = qs.filter(category__slug=category)
        if min_price:
            qs = qs.filter(price__gte=min_price)
        if max_price:
            qs = qs.filter(price__lte=max_price)
        if in_stock == '1':
            qs = qs.filter(stock__gt=0)
        return qs


class ProductDetailView(generics.RetrieveAPIView):
    queryset = Product.objects.filter(is_active=True)
    serializer_class = ProductDetailSerializer
    lookup_field = 'slug'
    permission_classes = [AllowAny]


# â”€â”€ Panier â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_cart(request):
    cart, _ = Cart.objects.get_or_create(user=request.user)
    serializer = CartSerializer(cart, context={'request': request})
    return Response(serializer.data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_cart_add(request):
    product_id = request.data.get('product_id')
    quantity = int(request.data.get('quantity', 1))
    product = get_object_or_404(Product, pk=product_id, is_active=True)
    cart, _ = Cart.objects.get_or_create(user=request.user)
    item, created = CartItem.objects.get_or_create(cart=cart, product=product)
    if not created:
        item.quantity += quantity
    else:
        item.quantity = quantity
    item.save()
    serializer = CartSerializer(cart, context={'request': request})
    return Response(serializer.data)


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def api_cart_update(request, item_id):
    item = get_object_or_404(CartItem, pk=item_id, cart__user=request.user)
    qty = int(request.data.get('quantity', 1))
    if qty <= 0:
        item.delete()
    else:
        item.quantity = qty
        item.save()
    cart = Cart.objects.get(user=request.user)
    return Response(CartSerializer(cart, context={'request': request}).data)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def api_cart_remove(request, item_id):
    item = get_object_or_404(CartItem, pk=item_id, cart__user=request.user)
    item.delete()
    cart = Cart.objects.get(user=request.user)
    return Response(CartSerializer(cart, context={'request': request}).data)


# â”€â”€ Commandes â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_order_list(request):
    orders = Order.objects.filter(user=request.user)
    serializer = OrderSerializer(orders, many=True, context={'request': request})
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_order_detail(request, pk):
    order = get_object_or_404(Order, pk=pk, user=request.user)
    return Response(OrderSerializer(order, context={'request': request}).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_checkout(request):
    cart = get_object_or_404(Cart, user=request.user)
    if not cart.cart_items.exists():
        return Response({'error': 'Panier vide.'}, status=400)

    address = request.data.get('shipping_address', '').strip()
    phone = request.data.get('phone', '').strip()
    if not address:
        return Response({'error': "L'adresse de livraison est obligatoire."}, status=400)
    if not phone:
        return Response({'error': "Le numéro de téléphone est obligatoire."}, status=400)

    loyalty, _ = LoyaltyAccount.objects.get_or_create(user=request.user)
    use_points = min(int(request.data.get('use_points', 0) or 0), loyalty.points)
    discount = (use_points // 10) * 400

    order = Order.objects.create(
        user=request.user,
        shipping_address=address,
        phone=phone,
        contact_email=request.data.get('contact_email', '').strip() or request.user.email,
        note=request.data.get('note', ''),
        discount=discount,
        payment_method=request.data.get('payment_method', 'cash'),
        payment_reference=request.data.get('payment_reference', '').strip(),
    )
    for ci in cart.cart_items.all():
        OrderItem.objects.create(
            order=order,
            product=ci.product,
            quantity=ci.quantity,
            unit_price=ci.product.price,
        )
        p = ci.product
        p.stock = max(0, p.stock - ci.quantity)
        p.save()

    earned = loyalty.add_points(order)
    if discount > 0 and use_points > 0:
        loyalty.use_points(use_points, order)

    cart.cart_items.all().delete()

    from .signals import send_order_email, send_admin_order_notification
    send_order_email(order, earned, loyalty)
    send_admin_order_notification(order)

    data = OrderSerializer(order, context={'request': request}).data
    data['loyalty_points_earned'] = earned
    return Response(data, status=201)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_order_receipt_pdf(request, pk):
    from django.http import HttpResponse
    from .views import build_order_receipt_pdf
    if request.user.is_staff:
        order = get_object_or_404(Order, pk=pk)
    else:
        order = get_object_or_404(Order, pk=pk, user=request.user)
    buffer = build_order_receipt_pdf(order, request.query_params.get('currency', 'GNF'))
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="recu-commande-{order.pk:06d}.pdf"'
    return response


# ── Avis produits ────────────────────────────────────────────────────────────

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_submit_review(request, product_id):
    product = get_object_or_404(Product, pk=product_id, is_active=True)
    rating = int(request.data.get('rating', 5))
    comment = request.data.get('comment', '').strip()
    review, _ = Review.objects.update_or_create(
        product=product, user=request.user,
        defaults={'rating': rating, 'comment': comment},
    )
    return Response(ReviewSerializer(review).data, status=201)


# ── Fidélité ──────────────────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_loyalty(request):
    loyalty, _ = LoyaltyAccount.objects.get_or_create(user=request.user)
    return Response(LoyaltyAccountSerializer(loyalty).data)


# ── Devises ───────────────────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([AllowAny])
def api_currencies(request):
    from .models import ExchangeRate
    rates = ExchangeRate.objects.all().order_by('currency_code')
    return Response([{
        'currency_code': r.currency_code,
        'currency_symbol': r.currency_symbol,
        'rate_from_gnf': float(r.rate_from_gnf),
    } for r in rates])

