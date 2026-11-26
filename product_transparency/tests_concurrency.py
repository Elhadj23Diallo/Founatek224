from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal
from threading import Barrier

from django.contrib.auth import get_user_model
from django.db import connection, connections
from django.test import TransactionTestCase
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from product_transparency.models import Company, Product, ProductPricing, Sale, SaleItem


class ConcurrentSaleTests(TransactionTestCase):
    def test_web_and_mobile_cannot_sell_the_same_last_unit(self):
        if connection.vendor == "sqlite" and connection.creation.is_in_memory_db(connection.settings_dict["NAME"]):
            self.skipTest("Use a file-backed SQLite test database for realistic writer contention")

        user = get_user_model().objects.create_user("concurrent-cashier")
        token, _ = Token.objects.get_or_create(user=user)
        company = Company.objects.create(user=user, name="Fixture", slug="concurrent-fixture")
        product, = Product.objects.bulk_create([
            Product(company=company, sku="last-unit", name="Last unit", stock=1),
        ])
        ProductPricing.objects.create(product=product, price=Decimal("2.50"),
            production_date=date(2026, 1, 1), expiry_date=date(2027, 1, 1))
        barrier = Barrier(2)

        def sell(route, product_id):
            try:
                client = APIClient()
                client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
                barrier.wait(timeout=10)
                response = client.post(route, {"items": [{"product_id": product_id, "quantity": 1}]}, format="json")
                return response.status_code
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            web = pool.submit(sell, "/product_transparency/api/sales/", str(product.uuid))
            mobile = pool.submit(sell, "/api/mobile/transparence/sales/create/", product.pk)
            self.assertIn(sorted([web.result(timeout=30), mobile.result(timeout=30)]), ([200, 400], [201, 400]))
        product.refresh_from_db()
        self.assertEqual(product.stock, 0)
        self.assertEqual(Sale.objects.filter(company=company).count(), 1)
        self.assertEqual(SaleItem.objects.filter(product=product).count(), 1)
