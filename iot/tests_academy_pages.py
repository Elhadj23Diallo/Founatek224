from django.test import TestCase
from django.urls import reverse


class AcademyBookPageTests(TestCase):
    def test_book_page_shows_all_chapters_without_opening_sales(self):
        response = self.client.get(reverse("iot:academy_book_home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Le catalogue de l")
        self.assertContains(response, "Chapitre 00")
        self.assertContains(response, "Chapitre 11")
        self.assertContains(response, "Les achats sont temporairement désactivés")
        self.assertNotContains(response, 'id="academy-buy-form"')
