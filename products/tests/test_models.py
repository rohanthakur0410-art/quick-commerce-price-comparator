from decimal import Decimal

from django.db import IntegrityError, transaction
from django.test import TestCase

from products.models import (
    Category, City, District, Locality, PlatformAvailability, Platform,
    Product, ProductOffer, State, Subcategory,
)


class GeoHierarchyTests(TestCase):
    def setUp(self):
        self.state = State.objects.create(name="Karnataka", code="KA")
        self.district = District.objects.create(name="Bengaluru Urban", state=self.state)
        self.city = City.objects.create(name="Bengaluru", district=self.district)

    def test_locality_str_and_state_property(self):
        locality = Locality.objects.create(city=self.city, name="Koramangala", pincode="560034")
        self.assertEqual(str(locality), "Koramangala, Bengaluru")
        self.assertEqual(locality.state, self.state)

    def test_unique_district_per_state(self):
        District.objects.create(name="Mysuru", state=self.state)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                District.objects.create(name="Mysuru", state=self.state)

    def test_unique_city_per_district(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                City.objects.create(name="Bengaluru", district=self.district)

    def test_unique_locality_per_city(self):
        Locality.objects.create(city=self.city, name="Indiranagar")
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Locality.objects.create(city=self.city, name="Indiranagar")

    def test_same_locality_name_different_city_allowed(self):
        other_city = City.objects.create(name="Mysuru", district=self.district)
        Locality.objects.create(city=self.city, name="Vijayanagar")
        Locality.objects.create(city=other_city, name="Vijayanagar")
        self.assertEqual(Locality.objects.filter(name="Vijayanagar").count(), 2)


class PlatformAvailabilityTests(TestCase):
    def setUp(self):
        state = State.objects.create(name="Karnataka", code="KA")
        district = District.objects.create(name="Bengaluru Urban", state=state)
        city = City.objects.create(name="Bengaluru", district=district)
        self.locality = Locality.objects.create(city=city, name="Koramangala")
        self.platform = Platform.objects.create(name="Blinkit", slug="blinkit")

    def test_str(self):
        avail = PlatformAvailability.objects.create(platform=self.platform, locality=self.locality, status=PlatformAvailability.AVAILABLE)
        self.assertIn("Blinkit", str(avail))
        self.assertIn("available", str(avail))

    def test_default_status_is_unknown(self):
        avail = PlatformAvailability.objects.create(platform=self.platform, locality=self.locality)
        self.assertEqual(avail.status, PlatformAvailability.UNKNOWN)

    def test_unique_platform_locality(self):
        PlatformAvailability.objects.create(platform=self.platform, locality=self.locality)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                PlatformAvailability.objects.create(platform=self.platform, locality=self.locality)


class ProductModelTests(TestCase):
    def setUp(self):
        category = Category.objects.create(name="Dairy & Breakfast")
        self.subcategory = Subcategory.objects.create(name="Milk", category=category)

    def test_normalized_name_set_on_save(self):
        product = Product.objects.create(
            name="Amul Taaza Toned Milk 1L", brand="Amul", subcategory=self.subcategory,
            quantity=Decimal("1.000"), unit="l",
        )
        self.assertEqual(product.normalized_name, "amul taaza toned milk")

    def test_category_property(self):
        product = Product.objects.create(
            name="Amul Gold Milk 500ml", brand="Amul", subcategory=self.subcategory,
            quantity=Decimal("0.500"), unit="l",
        )
        self.assertEqual(product.category.name, "Dairy & Breakfast")

    def test_dedup_constraint_blocks_true_duplicate(self):
        Product.objects.create(name="Amul Taaza Milk 1L", brand="Amul", subcategory=self.subcategory, quantity=Decimal("1.000"), unit="l")
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Product.objects.create(name="Amul Taaza Milk - 1 L", brand="Amul", subcategory=self.subcategory, quantity=Decimal("1.000"), unit="l")

    def test_different_quantity_is_not_a_duplicate(self):
        Product.objects.create(name="Amul Taaza Milk 500ml", brand="Amul", subcategory=self.subcategory, quantity=Decimal("0.500"), unit="l")
        Product.objects.create(name="Amul Taaza Milk 1L", brand="Amul", subcategory=self.subcategory, quantity=Decimal("1.000"), unit="l")
        self.assertEqual(Product.objects.count(), 2)

    def test_different_unit_is_not_a_duplicate_even_with_same_number(self):
        # Guards against "quantity must matter" false-matches: 1kg != 1L
        Product.objects.create(name="Rice 1", brand="Local", subcategory=self.subcategory, quantity=Decimal("1.000"), unit="kg")
        Product.objects.create(name="Oil 1", brand="Local", subcategory=self.subcategory, quantity=Decimal("1.000"), unit="l")
        self.assertEqual(Product.objects.count(), 2)


class ProductOfferModelTests(TestCase):
    def setUp(self):
        category = Category.objects.create(name="Grocery & Staples")
        subcategory = Subcategory.objects.create(name="Salt", category=category)
        self.product = Product.objects.create(name="Tata Salt 1kg", brand="Tata", subcategory=subcategory, quantity=Decimal("1.000"), unit="kg")
        self.platform = Platform.objects.create(name="Blinkit", slug="blinkit")
        state = State.objects.create(name="Karnataka", code="KA")
        district = District.objects.create(name="Bengaluru Urban", state=state)
        city = City.objects.create(name="Bengaluru", district=district)
        self.locality = Locality.objects.create(city=city, name="HSR Layout")

    def test_unique_offer_per_product_platform_locality(self):
        ProductOffer.objects.create(product=self.product, platform=self.platform, locality=self.locality, current_price=Decimal("28.00"))
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ProductOffer.objects.create(product=self.product, platform=self.platform, locality=self.locality, current_price=Decimal("30.00"))

    def test_is_demo_defaults_true(self):
        offer = ProductOffer.objects.create(product=self.product, platform=self.platform, locality=self.locality, current_price=Decimal("28.00"))
        self.assertTrue(offer.is_demo)
