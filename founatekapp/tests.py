from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Category, Product, Cart, CartItem, Order, ExchangeRate, Review


class ShopImprovementsTests(TestCase):
	def setUp(self):
		self.user = get_user_model().objects.create_user(username='alice', password='secret123')
		self.category = Category.objects.create(name='Capteurs', slug='capteurs')
		self.product = Product.objects.create(name='Capteur', slug='capteur', category=self.category, price=25000, stock=5)
		self.cart = Cart.objects.create(user=self.user)
		self.cart_item = CartItem.objects.create(cart=self.cart, product=self.product, quantity=2)
		ExchangeRate.objects.create(currency_code='USD', currency_symbol='$', rate_from_gnf=0.00012)

	def test_cart_add_requires_post(self):
		self.client.login(username='alice', password='secret123')
		response = self.client.get(reverse('founatekapp:cart_add', args=[self.product.pk]))
		self.assertRedirects(response, reverse('founatekapp:cart'))

	def test_checkout_accepts_payment_method(self):
		self.client.login(username='alice', password='secret123')
		response = self.client.post(reverse('founatekapp:checkout'), {
			'address': 'Conakry',
			'phone': '+224 666000000',
			'contact_email': 'alice@example.com',
			'payment_method': 'orange_money',
			'payment_reference': '+224 660000000',
		})
		self.assertEqual(response.status_code, 302)
		order = Order.objects.get(user=self.user)
		self.assertEqual(order.payment_method, 'orange_money')
		self.assertEqual(order.payment_reference, '+224 660000000')

	def test_currency_switch_is_stored_in_session(self):
		response = self.client.post(reverse('founatekapp:set_currency'), {'currency_code': 'USD'})
		self.assertEqual(self.client.session['currency_code'], 'USD')
		self.assertEqual(response.status_code, 302)

	def test_review_can_be_submitted(self):
		self.client.login(username='alice', password='secret123')
		response = self.client.post(reverse('founatekapp:submit_review', args=[self.product.pk]), {
			'rating': 5,
			'comment': 'Excellent produit',
		})
		self.assertEqual(response.status_code, 302)
		self.assertTrue(Review.objects.filter(product=self.product, user=self.user).exists())

