from decimal import Decimal

from django.test import TestCase

from products.models import (
    Category, City, District, Locality, PlatformAvailability, Platform,
    PriceHistory, Product, ProductOffer, State, Subcategory,
)
from products.services import compare_basket, compare_prices, compute_price_insights


class ServiceTestBase(TestCase):
    def setUp(self):
        state = State.objects.create(name="Karnataka", code="KA")
        district = District.objects.create(name="Bengaluru Urban", state=state)
        city = City.objects.create(name="Bengaluru", district=district)
        self.locality = Locality.objects.create(city=city, name="Koramangala")
        self.other_locality = Locality.objects.create(city=city, name="Whitefield")

        self.blinkit = Platform.objects.create(name="Blinkit", slug="blinkit", base_delivery_fee=Decimal("15.00"), free_delivery_above=Decimal("199.00"))
        self.zepto = Platform.objects.create(name="Zepto", slug="zepto", base_delivery_fee=Decimal("19.00"), free_delivery_above=Decimal("199.00"))

        for platform in [self.blinkit, self.zepto]:
            PlatformAvailability.objects.create(platform=platform, locality=self.locality, status=PlatformAvailability.AVAILABLE)

        category = Category.objects.create(name="Dairy & Breakfast")
        self.subcategory = Subcategory.objects.create(name="Milk", category=category)

    def make_product(self, name, brand="Amul", qty="1.000", unit="l"):
        return Product.objects.create(name=name, brand=brand, subcategory=self.subcategory, quantity=Decimal(qty), unit=unit)

    def make_offer(self, product, platform, price, available=True, locality=None):
        return ProductOffer.objects.create(
            product=product, platform=platform, locality=locality or self.locality,
            current_price=Decimal(price), is_available=available,
        )


class ComparePricesTests(ServiceTestBase):
    def test_cheapest_price_selection(self):
        product = self.make_product("Amul Taaza Milk 1L")
        self.make_offer(product, self.blinkit, "68.00")
        self.make_offer(product, self.zepto, "65.00")

        result = compare_prices(product, locality=self.locality)

        self.assertEqual(result.lowest_price, Decimal("65.00"))
        self.assertEqual(result.best_platform, "Zepto")

    def test_unavailable_offer_excluded_from_lowest_price(self):
        product = self.make_product("Amul Taaza Milk 1L")
        self.make_offer(product, self.blinkit, "60.00", available=False)
        self.make_offer(product, self.zepto, "70.00", available=True)

        result = compare_prices(product, locality=self.locality)

        self.assertEqual(result.lowest_price, Decimal("70.00"))
        self.assertEqual(result.available_count, 1)
        self.assertEqual(result.total_count, 2)

    def test_platform_with_no_availability_row_shown_as_unserviceable(self):
        # A third platform with an offer row but NO PlatformAvailability
        # entry must still be listed (per the "show all platforms"
        # requirement) but marked not-serviceable, with no price ever
        # fabricated for it - fail-closed on the PRICE, not on visibility.
        PlatformAvailability.objects.filter(platform=self.zepto, locality=self.locality).delete()
        rogue_platform = Platform.objects.create(name="Rogue Platform", slug="rogue")
        product = self.make_product("Amul Taaza Milk 1L")
        self.make_offer(product, self.blinkit, "68.00")
        self.make_offer(product, rogue_platform, "1.00")  # absurdly cheap - must not win, must not show

        result = compare_prices(product, locality=self.locality)

        self.assertEqual(result.lowest_price, Decimal("68.00"))
        rogue_row = next(r for r in result.rows if r.platform_name == "Rogue Platform")
        self.assertFalse(rogue_row.serviceable)
        self.assertIsNone(rogue_row.price)
        self.assertFalse(rogue_row.is_available)

    def test_never_mixes_localities(self):
        product = self.make_product("Amul Taaza Milk 1L")
        self.make_offer(product, self.blinkit, "68.00", locality=self.locality)
        PlatformAvailability.objects.create(platform=self.blinkit, locality=self.other_locality, status=PlatformAvailability.AVAILABLE)
        self.make_offer(product, self.zepto, "10.00", locality=self.other_locality)
        PlatformAvailability.objects.filter(platform=self.zepto, locality=self.locality).delete()

        result = compare_prices(product, locality=self.locality)

        self.assertEqual(result.lowest_price, Decimal("68.00"))
        # Zepto still appears (all active platforms are always listed),
        # but as "not available in this area", never with the other
        # locality's ₹10.00 price.
        zepto_row = next(r for r in result.rows if r.platform_name == "Zepto")
        self.assertFalse(zepto_row.serviceable)
        self.assertIsNone(zepto_row.price)

    def test_empty_when_no_offers(self):
        product = self.make_product("Amul Taaza Milk 1L")
        # other_locality has no PlatformAvailability rows configured in
        # setUp, so nothing is priced here - but every active platform is
        # still listed, as "not available in this area".
        result = compare_prices(product, locality=self.other_locality)
        self.assertIsNone(result.lowest_price)
        self.assertEqual(result.available_count, 0)
        self.assertTrue(all(not r.serviceable and r.price is None for r in result.rows))
        self.assertEqual(len(result.rows), 2)  # blinkit + zepto, both unserviceable here


class PriceInsightsTests(ServiceTestBase):
    def test_no_history_returns_empty(self):
        product = self.make_product("Tata Salt 1kg")
        insights = compute_price_insights(product, locality=self.locality)
        self.assertEqual(insights.sample_size, 0)

    def test_change_amount_and_lowest_highest(self):
        product = self.make_product("Tata Salt 1kg")
        offer = self.make_offer(product, self.blinkit, "28.00")
        PriceHistory.objects.create(product_offer=offer, price=Decimal("30.00"))
        PriceHistory.objects.create(product_offer=offer, price=Decimal("28.00"))
        PriceHistory.objects.create(product_offer=offer, price=Decimal("32.00"))

        insights = compute_price_insights(product, locality=self.locality)

        self.assertEqual(insights.current_price, Decimal("32.00"))
        self.assertEqual(insights.previous_price, Decimal("28.00"))
        self.assertEqual(insights.lowest_recorded, Decimal("28.00"))
        self.assertEqual(insights.highest_recorded, Decimal("32.00"))


class CompareBasketTests(ServiceTestBase):
    def test_single_platform_totals_and_best(self):
        milk = self.make_product("Amul Taaza Milk 1L")
        bread = self.make_product("Britannia Bread 400g", brand="Britannia")
        self.make_offer(milk, self.blinkit, "70.00")
        self.make_offer(milk, self.zepto, "65.00")
        self.make_offer(bread, self.blinkit, "40.00")
        self.make_offer(bread, self.zepto, "45.00")

        result = compare_basket([(milk, 1), (bread, 1)], self.locality)

        blinkit_total = next(t for t in result.single_platform_totals if t.platform_name == "Blinkit")
        zepto_total = next(t for t in result.single_platform_totals if t.platform_name == "Zepto")
        self.assertTrue(blinkit_total.can_fulfill_all)
        self.assertEqual(blinkit_total.subtotal, Decimal("110.00"))
        self.assertEqual(zepto_total.subtotal, Decimal("110.00"))
        self.assertIsNotNone(result.best_single_platform)

    def test_platform_that_cannot_fulfill_all_is_excluded_from_best(self):
        milk = self.make_product("Amul Taaza Milk 1L")
        bread = self.make_product("Britannia Bread 400g", brand="Britannia")
        self.make_offer(milk, self.blinkit, "70.00")
        self.make_offer(milk, self.zepto, "65.00")
        self.make_offer(bread, self.blinkit, "40.00")
        # Zepto's bread listing exists but is out of stock -> can't
        # fulfill the whole basket. (Explicitly marked unavailable
        # rather than omitted, so compare_basket's lazy materialization
        # doesn't paper over it with a freshly generated demo price.)
        self.make_offer(bread, self.zepto, "42.00", available=False)

        result = compare_basket([(milk, 1), (bread, 1)], self.locality)

        zepto_total = next(t for t in result.single_platform_totals if t.platform_name == "Zepto")
        self.assertFalse(zepto_total.can_fulfill_all)
        self.assertEqual(result.best_single_platform.platform_name, "Blinkit")

    def test_delivery_fee_waived_above_threshold(self):
        milk = self.make_product("Amul Taaza Milk 1L")
        PlatformAvailability.objects.filter(platform=self.zepto, locality=self.locality).delete()
        self.make_offer(milk, self.blinkit, "250.00")  # above free_delivery_above=199

        result = compare_basket([(milk, 1)], self.locality)

        blinkit_total = next(t for t in result.single_platform_totals if t.platform_name == "Blinkit")
        self.assertEqual(blinkit_total.delivery_fee, Decimal("0.00"))

    def test_delivery_fee_applies_below_threshold(self):
        milk = self.make_product("Amul Taaza Milk 1L")
        PlatformAvailability.objects.filter(platform=self.zepto, locality=self.locality).delete()
        self.make_offer(milk, self.blinkit, "50.00")  # below free_delivery_above=199

        result = compare_basket([(milk, 1)], self.locality)

        blinkit_total = next(t for t in result.single_platform_totals if t.platform_name == "Blinkit")
        self.assertEqual(blinkit_total.delivery_fee, Decimal("15.00"))

    def test_split_not_recommended_when_savings_below_threshold(self):
        milk = self.make_product("Amul Taaza Milk 1L")
        bread = self.make_product("Britannia Bread 400g", brand="Britannia")
        # Prices nearly identical -> any split savings will be eaten by
        # a second delivery fee, so a split should never be recommended.
        self.make_offer(milk, self.blinkit, "70.00")
        self.make_offer(milk, self.zepto, "69.50")
        self.make_offer(bread, self.blinkit, "40.00")
        self.make_offer(bread, self.zepto, "39.50")

        result = compare_basket([(milk, 1), (bread, 1)], self.locality)

        self.assertFalse(result.recommend_split)

    def test_explanation_lists_per_item_savings(self):
        milk = self.make_product("Amul Taaza Milk 1L")
        self.make_offer(milk, self.blinkit, "80.00")
        self.make_offer(milk, self.zepto, "60.00")

        result = compare_basket([(milk, 1)], self.locality)

        self.assertTrue(any("20" in line for line in result.explanation))

    def test_empty_basket_handled_gracefully(self):
        result = compare_basket([], self.locality)
        self.assertEqual(result.items, [])
