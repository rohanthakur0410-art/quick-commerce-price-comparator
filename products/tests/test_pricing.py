from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase

from products.models import (
    Category, City, District, Locality, PlatformAvailability, Platform,
    PriceHistory, Product, ProductOffer, State, Subcategory,
)
from products.pricing import available_platforms_for, ensure_offers, refresh_offers_for, upsert_offer
from scrapers.base_scraper import ProviderOffer, ScraperError


class PricingTestBase(TestCase):
    def setUp(self):
        state = State.objects.create(name="Karnataka", code="KA")
        district = District.objects.create(name="Bengaluru Urban", state=state)
        city = City.objects.create(name="Bengaluru", district=district)
        self.locality = Locality.objects.create(city=city, name="Koramangala")
        self.other_locality = Locality.objects.create(city=city, name="Whitefield")

        self.blinkit = Platform.objects.create(name="Blinkit", slug="blinkit")
        self.zepto = Platform.objects.create(name="Zepto", slug="zepto")

        category = Category.objects.create(name="Dairy & Breakfast")
        subcategory = Subcategory.objects.create(name="Milk", category=category)
        self.product = Product.objects.create(
            name="Amul Taaza Milk 1L", brand="Amul", subcategory=subcategory, quantity=Decimal("1.000"), unit="l"
        )


class AvailablePlatformsForTests(PricingTestBase):
    def test_fail_closed_when_no_availability_row(self):
        # No PlatformAvailability rows at all -> nothing is available.
        self.assertEqual(list(available_platforms_for(self.locality)), [])

    def test_only_available_status_counts(self):
        PlatformAvailability.objects.create(platform=self.blinkit, locality=self.locality, status=PlatformAvailability.AVAILABLE)
        PlatformAvailability.objects.create(platform=self.zepto, locality=self.locality, status=PlatformAvailability.UNAVAILABLE)
        platforms = list(available_platforms_for(self.locality))
        self.assertEqual(platforms, [self.blinkit])

    def test_unknown_status_is_not_shown(self):
        PlatformAvailability.objects.create(platform=self.blinkit, locality=self.locality, status=PlatformAvailability.UNKNOWN)
        self.assertEqual(list(available_platforms_for(self.locality)), [])


class UpsertOfferTests(PricingTestBase):
    def test_creates_offer_and_history(self):
        with patch("scrapers.blinkit.BlinkitScraper.get_offer", return_value=ProviderOffer(
            external_product_id="x", source_url="https://x.demo", price=66.0, is_available=True, delivery_minutes=10,
        )):
            offer, error = upsert_offer(self.product, self.blinkit, self.locality)
        self.assertIsNone(error)
        self.assertEqual(offer.current_price, Decimal("66.0"))
        self.assertEqual(PriceHistory.objects.filter(product_offer=offer).count(), 1)

    def test_provider_failure_returns_error_not_exception(self):
        with patch("scrapers.blinkit.BlinkitScraper.get_offer", side_effect=ScraperError("simulated")):
            offer, error = upsert_offer(self.product, self.blinkit, self.locality)
        self.assertIsNone(offer)
        self.assertIn("simulated", error)

    def test_unchanged_price_does_not_duplicate_history(self):
        with patch("scrapers.blinkit.BlinkitScraper.get_offer", return_value=ProviderOffer(
            external_product_id="x", source_url="https://x.demo", price=66.0, is_available=True,
        )):
            upsert_offer(self.product, self.blinkit, self.locality)
            upsert_offer(self.product, self.blinkit, self.locality)
        offer = ProductOffer.objects.get(product=self.product, platform=self.blinkit, locality=self.locality)
        self.assertEqual(PriceHistory.objects.filter(product_offer=offer).count(), 1)

    def test_changed_price_creates_new_history_row(self):
        with patch("scrapers.blinkit.BlinkitScraper.get_offer", return_value=ProviderOffer(
            external_product_id="x", source_url="https://x.demo", price=66.0, is_available=True,
        )):
            upsert_offer(self.product, self.blinkit, self.locality)
        with patch("scrapers.blinkit.BlinkitScraper.get_offer", return_value=ProviderOffer(
            external_product_id="x", source_url="https://x.demo", price=60.0, is_available=True,
        )):
            offer, _ = upsert_offer(self.product, self.blinkit, self.locality)
        self.assertEqual(offer.current_price, Decimal("60.0"))
        self.assertEqual(PriceHistory.objects.filter(product_offer=offer).count(), 2)


class EnsureOffersTests(PricingTestBase):
    @patch("random.random", return_value=0.99)
    def test_materializes_only_available_platforms(self, mock_random):
        # Pinned above Blinkit's failure_rate/out_of_stock_rate so this
        # exercises "does an offer get created", not the simulated-
        # failure path.
        PlatformAvailability.objects.create(platform=self.blinkit, locality=self.locality, status=PlatformAvailability.AVAILABLE)
        PlatformAvailability.objects.create(platform=self.zepto, locality=self.locality, status=PlatformAvailability.UNAVAILABLE)

        ensure_offers(self.product, self.locality)

        self.assertTrue(ProductOffer.objects.filter(product=self.product, platform=self.blinkit, locality=self.locality).exists())
        self.assertFalse(ProductOffer.objects.filter(product=self.product, platform=self.zepto, locality=self.locality).exists())

    def test_does_not_re_materialize_existing_offer(self):
        PlatformAvailability.objects.create(platform=self.blinkit, locality=self.locality, status=PlatformAvailability.AVAILABLE)
        ProductOffer.objects.create(product=self.product, platform=self.blinkit, locality=self.locality, current_price=Decimal("50.00"))

        ensure_offers(self.product, self.locality)

        offer = ProductOffer.objects.get(product=self.product, platform=self.blinkit, locality=self.locality)
        self.assertEqual(offer.current_price, Decimal("50.00"))  # untouched
        self.assertEqual(ProductOffer.objects.filter(product=self.product, platform=self.blinkit, locality=self.locality).count(), 1)

    def test_never_materializes_for_a_different_locality(self):
        PlatformAvailability.objects.create(platform=self.blinkit, locality=self.locality, status=PlatformAvailability.AVAILABLE)
        ensure_offers(self.product, self.locality)
        self.assertFalse(ProductOffer.objects.filter(product=self.product, locality=self.other_locality).exists())


class RefreshOffersForTests(PricingTestBase):
    def test_refreshes_existing_offer_regardless_of_age(self):
        PlatformAvailability.objects.create(platform=self.blinkit, locality=self.locality, status=PlatformAvailability.AVAILABLE)
        ProductOffer.objects.create(product=self.product, platform=self.blinkit, locality=self.locality, current_price=Decimal("50.00"))

        with patch("scrapers.blinkit.BlinkitScraper.get_offer", return_value=ProviderOffer(
            external_product_id="x", source_url="https://x.demo", price=45.0, is_available=True,
        )):
            touched, errors = refresh_offers_for(self.product, self.locality)

        self.assertEqual(touched, 1)
        self.assertEqual(errors, [])
        offer = ProductOffer.objects.get(product=self.product, platform=self.blinkit, locality=self.locality)
        self.assertEqual(offer.current_price, Decimal("45.0"))
