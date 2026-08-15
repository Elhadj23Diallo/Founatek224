from decimal import Decimal
from django.db import models
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils.text import slugify


class Category(models.Model):
    name = models.CharField(max_length=200)
    slug = models.SlugField(unique=True, blank=True)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to='categories/', blank=True, null=True)

    class Meta:
        verbose_name_plural = 'Categories'
        ordering = ['name']

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('founatekapp:category', kwargs={'slug': self.slug})


class Product(models.Model):
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='products')
    name = models.CharField(max_length=300)
    slug = models.SlugField(unique=True, blank=True)
    description = models.TextField(blank=True)
    specifications = models.TextField(blank=True, help_text='Fiche technique (datasheet, pinout, etc.)')
    price = models.DecimalField(max_digits=10, decimal_places=2)
    stock = models.PositiveIntegerField(default=0)
    image = models.ImageField(upload_to='products/', blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('founatekapp:product_detail', kwargs={'slug': self.slug})

    @property
    def in_stock(self):
        return self.stock > 0

    @property
    def average_rating(self):
        return self.reviews.aggregate(models.Avg('rating'))['rating__avg'] or 0

    @property
    def review_count(self):
        return self.reviews.count()

    def get_all_images(self):
        """Retourne la liste complète des images : image principale + galerie."""
        images = []
        if self.image:
            images.append(self.image.url)
        for img in self.gallery.order_by('order'):
            images.append(img.image.url)
        return images


class ProductImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='gallery')
    image = models.ImageField(upload_to='products/gallery/')
    alt = models.CharField(max_length=200, blank=True)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f'Image #{self.order} â€” {self.product.name}'


class Order(models.Model):
    STATUS_CHOICES = [
        ('pending', 'En attente'),
        ('confirmed', 'Confirmée'),
        ('shipped', 'Expédiée'),
        ('delivered', 'Livrée'),
        ('cancelled', 'Annulée'),
    ]
    PAYMENT_METHOD_CHOICES = [
        ('cash', 'Paiement manuel / cash'),
        ('orange_money', 'Orange Money'),
        ('mtn_momo', 'MTN MoMo'),
    ]
    PAYMENT_STATUS_CHOICES = [
        ('pending', 'En attente'),
        ('paid', 'Payée'),
        ('failed', 'Échouée'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='orders')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES, default='cash')
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='pending')
    payment_reference = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    shipping_address = models.TextField(blank=True)
    phone = models.CharField(max_length=30, blank=True)
    contact_email = models.EmailField(blank=True)
    note = models.TextField(blank=True)
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'Commande #{self.pk} â€” {self.user.username}'

    def get_absolute_url(self):
        return reverse('founatekapp:order_detail', kwargs={'pk': self.pk})

    @property
    def subtotal(self):
        return sum(item.subtotal for item in self.items.all())

    @property
    def total(self):
        return max(0, self.subtotal - self.discount)

    @property
    def total_items(self):
        return sum(item.quantity for item in self.items.all())


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f'{self.quantity}x {self.product.name}'

    @property
    def subtotal(self):
        if self.unit_price is None or self.quantity is None:
            return 0
        return self.unit_price * self.quantity


class Cart(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='cart')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'Panier de {self.user.username}'

    @property
    def total(self):
        return sum(item.subtotal for item in self.cart_items.all())

    @property
    def total_items(self):
        return sum(item.quantity for item in self.cart_items.all())


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='cart_items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)

    class Meta:
        unique_together = ('cart', 'product')

    def __str__(self):
        return f'{self.quantity}x {self.product.name}'

    @property
    def subtotal(self):
        return self.product.price * self.quantity


class ExchangeRate(models.Model):
    currency_code = models.CharField(max_length=3, unique=True)
    currency_symbol = models.CharField(max_length=5)
    rate_from_gnf = models.DecimalField(max_digits=12, decimal_places=6)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['currency_code']

    def __str__(self):
        return f'{self.currency_code} ({self.currency_symbol})'


class Review(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='reviews')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reviews')
    rating = models.PositiveSmallIntegerField(default=5)
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        unique_together = ('product', 'user')

    def __str__(self):
        return f'{self.user} — {self.rating}★ on {self.product}'

    @property
    def average_rating(self):
        return self.product.reviews.aggregate(models.Avg('rating'))['rating__avg'] or 0


class LoyaltyAccount(models.Model):
    LEVELS = [
        ('bronze',   'Bronze'),
        ('argent',   'Argent'),
        ('or',       'Or'),
        ('platine',  'Platine'),
    ]
    # Seuils en points pour changer de niveau
    LEVEL_THRESHOLDS = {'bronze': 0, 'argent': 100, 'or': 300, 'platine': 700}
    LEVEL_COLORS     = {'bronze': '#cd7f32', 'argent': '#aaa9ad', 'or': '#ffd700', 'platine': '#00d2ff'}
    LEVEL_ICONS      = {'bronze': 'bi-award', 'argent': 'bi-award-fill', 'or': 'bi-trophy', 'platine': 'bi-trophy-fill'}

    user         = models.OneToOneField(User, on_delete=models.CASCADE, related_name='loyalty')
    points       = models.PositiveIntegerField(default=0)
    total_spent  = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    level        = models.CharField(max_length=10, choices=LEVELS, default='bronze')
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'Fidelite {self.user.username} â€” {self.points} pts ({self.level})'

    def update_level(self):
        if self.points >= 700:
            self.level = 'platine'
        elif self.points >= 300:
            self.level = 'or'
        elif self.points >= 100:
            self.level = 'argent'
        else:
            self.level = 'bronze'

    def add_points(self, order):
        """1 point par tranche de 2 000 GNF dépensée."""
        earned = int(order.total // 2000)
        if earned > 0:
            self.points += earned
            self.total_spent += order.total
            self.update_level()
            self.save()
            LoyaltyTransaction.objects.create(
                account=self,
                points=earned,
                kind='earn',
                description=f'Commande #{order.pk}',
                order=order,
            )
        return earned

    def use_points(self, points_used, order):
        """Utilise des points pour une remise (10 pts = 400 GNF)."""
        if points_used > self.points:
            raise ValueError('Points insuffisants')
        self.points -= points_used
        self.update_level()
        self.save()
        LoyaltyTransaction.objects.create(
            account=self,
            points=-points_used,
            kind='redeem',
            description=f'Remise commande #{order.pk}',
            order=order,
        )

    @property
    def discount_value(self):
        """Valeur GNF des points : 10 pts = 400 GNF."""
        return (self.points // 10) * 400

    @property
    def next_level_info(self):
        thresholds = [('bronze', 0), ('argent', 100), ('or', 300), ('platine', 700)]
        for name, threshold in thresholds:
            if self.points < threshold:
                return {'name': name, 'needed': threshold - self.points, 'threshold': threshold}
        return None

    @property
    def level_color(self):
        return self.LEVEL_COLORS.get(self.level, '#aaa')

    @property
    def level_icon(self):
        return self.LEVEL_ICONS.get(self.level, 'bi-award')


class LoyaltyTransaction(models.Model):
    KIND_CHOICES = [('earn', 'Points gagnés'), ('redeem', 'Points utilisés')]

    account     = models.ForeignKey(LoyaltyAccount, on_delete=models.CASCADE, related_name='transactions')
    points      = models.IntegerField()
    kind        = models.CharField(max_length=10, choices=KIND_CHOICES)
    description = models.CharField(max_length=200)
    order       = models.ForeignKey('Order', on_delete=models.SET_NULL, null=True, blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.kind} {self.points} pts â€” {self.account.user.username}'


def get_display_price(price, currency_code=None, rate=None):
    if currency_code and currency_code.upper() != 'GNF':
        if rate is None:
            rate = Decimal('1')
        return price * rate
    return price

