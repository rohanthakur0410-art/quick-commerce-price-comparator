from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase

from products.models import Category, City, District, Locality, Product, State, Subcategory
from scrapers.base_scraper import ScraperError
from scrapers.blinkit import BlinkitScraper
from scrapers.mock_scraper import base_price_for_product
from scrapers.registry import SCRAPER_REGISTRY, get_scraper_for_platform
from scrapers.zepto import ZeptoScraper


class ScraperTestBase(TestCase):
    def setUp(self):
        state = State.objects.create(name="Karnataka", code="KA")
        district = District.objects.create(name="Bengaluru Urban", state=state)
        city = City.objects.create(name="Bengaluru", district=district)
        self.locality = Locality.objects.create(city=city, name="Koramangala")
        category = Category.objects.create(name="Dairy & Breakfast")
        subcategory = Subcategory.objects.create(name="Milk", category=category)
        self.product = Product.objects.create(
            name="Amul Taaza Milk 1L", brand="Amul", subcategory=subcategory, quantity=Decimal("1.000"), unit="l"
        )


class BasePriceTests(ScraperTestBase):
    def test_base_price_is_deterministic(self):
        price1 = base_price_for_product(self.product)
        price2 = base_price_for_product(self.product)
        self.assertEqual(price1, price2)

    def test_larger_pack_costs_more_but_sublinearly(self):
        category = self.product.subcategory.category
        subcategory = self.product.subcategory
        small = Product.objects.create(name="Aashirvaad Atta 1kg", brand="Aashirvaad", subcategory=subcategory, quantity=Decimal("1.000"), unit="kg")
        large = Product.objects.create(name="Aashirvaad Atta 10kg", brand="Aashirvaad", subcategory=subcategory, quantity=Decimal("10.000"), unit="kg")
        price_small = base_price_for_product(small)
        price_large = base_price_for_product(large)
        self.assertGreater(price_large, price_small)
        self.assertLess(price_large, price_small * 10)  # bulk discount, not linear


class BlinkitScraperTests(ScraperTestBase):
    @patch("random.random", return_value=0.99)
    def test_get_offer_returns_provider_offer(self, mock_random):
        scraper = BlinkitScraper()
        offer = scraper.get_offer(self.product, self.locality)
        self.assertIsInstance(offer.price, float)
        self.assertGreater(offer.price, 0)
        self.assertTrue(offer.source_url.startswith("https://"))
        self.assertIn(self.product.sku, offer.external_product_id)

    @patch("random.random", return_value=0.0)
    def test_simulated_failure_raises_scraper_error(self, mock_random):
        scraper = BlinkitScraper()
        scraper.failure_rate = 1.0
        with self.assertRaises(ScraperError):
            scraper.get_offer(self.product, self.locality)

    def test_refresh_offers_is_alias_for_get_offer(self):
        scraper = BlinkitScraper()
        with patch.object(scraper, "get_offer") as mock_get:
            scraper.refresh_offers(self.product, self.locality)
            mock_get.assert_called_once_with(self.product, self.locality)


class PlatformDifferenceTests(ScraperTestBase):
    @patch("random.random", return_value=0.99)
    @patch("random.uniform", return_value=0.0)
    def test_platforms_price_differently(self, mock_uniform, mock_random):
        blinkit_offer = BlinkitScraper().get_offer(self.product, self.locality)
        zepto_offer = ZeptoScraper().get_offer(self.product, self.locality)
        # Different price_multiplier per platform -> different prices for
        # the identical product/locality (with noise pinned to 0).
        self.assertNotEqual(blinkit_offer.price, zepto_offer.price)


class RegistryTests(TestCase):
    def test_registry_has_five_platforms(self):
        self.assertEqual(len(SCRAPER_REGISTRY), 5)
        for name in ["Blinkit", "Zepto", "Swiggy Instamart", "Flipkart Minutes", "BigBasket"]:
            self.assertIn(name, SCRAPER_REGISTRY)

    def test_get_scraper_for_known_platform(self):
        scraper = get_scraper_for_platform("Zepto")
        self.assertEqual(scraper.platform_name, "Zepto")

    def test_get_scraper_for_unknown_platform_returns_none(self):
        self.assertIsNone(get_scraper_for_platform("Not A Real Platform"))
