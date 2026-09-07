from decimal import Decimal

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from products.models import (
    Category, City, District, Locality, PlatformAvailability, Platform,
    PriceHistory, Product, ProductOffer, State, Subcategory,
)


class ApiTestBase(APITestCase):
    def setUp(self):
        state = State.objects.create(name="Karnataka", code="KA")
        district = District.objects.create(name="Bengaluru Urban", state=state)
        city = City.objects.create(name="Bengaluru", district=district)
        self.locality = Locality.objects.create(city=city, name="Koramangala", pincode="560034")

        self.blinkit = Platform.objects.create(name="Blinkit", slug="blinkit")
        self.zepto = Platform.objects.create(name="Zepto", slug="zepto")
        for p in [self.blinkit, self.zepto]:
            PlatformAvailability.objects.create(platform=p, locality=self.locality, status=PlatformAvailability.AVAILABLE)

        category = Category.objects.create(name="Dairy & Breakfast")
        self.subcategory = Subcategory.objects.create(name="Milk", category=category)


class ProductSearchApiTests(ApiTestBase):
    def setUp(self):
        super().setUp()
        Product.objects.create(name="Amul Taaza Milk 1L", brand="Amul", subcategory=self.subcategory, quantity=Decimal("1.000"), unit="l")
        bakery_category = Category.objects.create(name="Bakery")
        bakery = Subcategory.objects.create(name="Bread", category=bakery_category)
        Product.objects.create(name="Britannia Brown Bread 400g", brand="Britannia", subcategory=bakery, quantity=Decimal("400.000"), unit="g")

    def test_list_all(self):
        response = self.client.get(reverse("api-product-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 2)

    def test_search_by_name(self):
        response = self.client.get(reverse("api-product-list"), {"search": "milk"})
        self.assertEqual(response.data["count"], 1)

    def test_search_by_brand(self):
        response = self.client.get(reverse("api-product-list"), {"search": "britannia"})
        self.assertEqual(response.data["count"], 1)

    def test_search_by_subcategory(self):
        response = self.client.get(reverse("api-product-list"), {"search": "bread"})
        self.assertEqual(response.data["count"], 1)

    def test_search_no_match(self):
        response = self.client.get(reverse("api-product-list"), {"search": "nonexistent"})
        self.assertEqual(response.data["count"], 0)

    def test_category_filter(self):
        response = self.client.get(reverse("api-product-list"), {"category": "Dairy & Breakfast"})
        self.assertEqual(response.data["count"], 1)


class ProductCompareApiTests(ApiTestBase):
    def setUp(self):
        super().setUp()
        self.product = Product.objects.create(name="Amul Taaza Milk 1L", brand="Amul", subcategory=self.subcategory, quantity=Decimal("1.000"), unit="l")
        ProductOffer.objects.create(product=self.product, platform=self.blinkit, locality=self.locality, current_price=Decimal("68.00"), is_available=True)
        ProductOffer.objects.create(product=self.product, platform=self.zepto, locality=self.locality, current_price=Decimal("65.00"), is_available=True)

    def test_compare_requires_locality(self):
        response = self.client.get(reverse("api-product-compare", args=[self.product.id]))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_compare_returns_best_price(self):
        response = self.client.get(reverse("api-product-compare", args=[self.product.id]), {"locality": self.locality.id})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["best_price"]["platform"], "Zepto")

    def test_compare_invalid_product_404(self):
        response = self.client.get(reverse("api-product-compare", args=[99999]), {"locality": self.locality.id})
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_compare_invalid_locality_404(self):
        response = self.client.get(reverse("api-product-compare", args=[self.product.id]), {"locality": 99999})
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class ProductHistoryApiTests(ApiTestBase):
    def setUp(self):
        super().setUp()
        self.product = Product.objects.create(name="Tata Salt 1kg", brand="Tata", subcategory=self.subcategory, quantity=Decimal("1.000"), unit="kg")
        offer = ProductOffer.objects.create(product=self.product, platform=self.blinkit, locality=self.locality, current_price=Decimal("28.00"))
        PriceHistory.objects.create(product_offer=offer, price=Decimal("27.00"))
        PriceHistory.objects.create(product_offer=offer, price=Decimal("28.00"))

    def test_history_and_insights(self):
        response = self.client.get(reverse("api-product-history", args=[self.product.id]), {"locality": self.locality.id})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 2)
        self.assertEqual(response.data["insights"]["current_price"], "28.00")

    def test_history_invalid_product_404(self):
        response = self.client.get(reverse("api-product-history", args=[99999]))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class LocalityApiTests(ApiTestBase):
    def test_search_by_name(self):
        response = self.client.get(reverse("api-locality-list"), {"q": "Koramangala"})
        self.assertEqual(response.data["count"], 1)

    def test_search_by_pincode(self):
        response = self.client.get(reverse("api-locality-list"), {"q": "560034"})
        self.assertEqual(response.data["count"], 1)

    def test_search_by_city(self):
        response = self.client.get(reverse("api-locality-list"), {"q": "Bengaluru"})
        self.assertEqual(response.data["count"], 1)

    def test_locality_includes_hierarchy(self):
        response = self.client.get(reverse("api-locality-list"), {"q": "Koramangala"})
        result = response.data["results"][0]
        self.assertEqual(result["city"], "Bengaluru")
        self.assertEqual(result["state"], "Karnataka")


class BasketCompareApiTests(ApiTestBase):
    def setUp(self):
        super().setUp()
        self.milk = Product.objects.create(name="Amul Taaza Milk 1L", brand="Amul", subcategory=self.subcategory, quantity=Decimal("1.000"), unit="l")
        ProductOffer.objects.create(product=self.milk, platform=self.blinkit, locality=self.locality, current_price=Decimal("68.00"))
        ProductOffer.objects.create(product=self.milk, platform=self.zepto, locality=self.locality, current_price=Decimal("65.00"))

    def test_basket_requires_locality(self):
        response = self.client.post(reverse("api-basket-compare"), {"items": [{"product_id": self.milk.id, "quantity": 1}]}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_basket_compare_success(self):
        response = self.client.post(reverse("api-basket-compare"), {
            "locality_id": self.locality.id, "items": [{"product_id": self.milk.id, "quantity": 2}],
        }, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["items"]), 1)

    def test_basket_unknown_product_404(self):
        response = self.client.post(reverse("api-basket-compare"), {
            "locality_id": self.locality.id, "items": [{"product_id": 99999, "quantity": 1}],
        }, format="json")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
