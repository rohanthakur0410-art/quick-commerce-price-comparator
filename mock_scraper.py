"""
Shared demo/mock provider engine.

IMPORTANT (see README "Demo vs Live data"):
Quick-commerce platforms require a logged-in/located session, resolve
prices by delivery area, and are protected by anti-bot measures. Scraping
them without authorization would violate their terms of service, which
this project does not do - and does not attempt to work around (no
CAPTCHA bypass, no auth abuse, no rate-limit circumvention).

Instead, every platform adapter (blinkit.py, zepto.py, instamart.py,
flipkart_minutes.py, bigbasket.py) is a demo adapter built on this shared
engine. Given a canonical Product and a Locality, it derives a
deterministic-but-varying base price from the product's own attributes
(brand+name+category band+pack size), then applies a platform-specific
multiplier, a locality cost index, and small run-to-run noise - so
prices differ sensibly by platform and place without a hand-maintained
price list for 2000+ products, and every ProductOffer.is_demo stays True.
"""

import hashlib
import logging
import random

from .base_scraper import BaseScraper, ProviderOffer, ScraperError

logger = logging.getLogger("scrapers")

# Rough price-per-base-unit band by top-level category, in rupees. Not a
# precise market model - just enough spread that a kilo of rice and a
# pack of AA batteries don't cost the same, and different categories feel
# distinct in the UI.
CATEGORY_PRICE_BANDS = {
    "Grocery & Staples": (25, 180),
    "Dairy & Breakfast": (20, 250),
    "Snacks & Packaged Food": (10, 120),
    "Beverages": (15, 150),
    "Fruits & Vegetables": (20, 90),
    "Frozen Food": (60, 350),
    "Personal Care": (40, 350),
    "Baby Care": (100, 600),
    "Household": (40, 300),
    "Pet Care": (80, 500),
    "Home & Kitchen": (100, 1200),
    "Stationery": (20, 200),
    "Electronics & Accessories": (150, 1500),
}
_DEFAULT_BAND = (30, 150)

PROMOTIONS = ["10% OFF", "Flat \u20b920 OFF", "Buy 1 Get 1", "5% Cashback", "Extra 5% OFF"]


def _size_factor(quantity: float, unit: str) -> float:
    """Convert a pack size to a rough 'how much bigger than baseline'
    multiplier, with sublinear scaling (bulk packs cost more but not
    proportionally more - a bulk-buy discount, same as real retail)."""
    if unit == "kg":
        base = quantity
    elif unit == "g":
        base = quantity / 1000
    elif unit == "l":
        base = quantity
    elif unit == "ml":
        base = quantity / 1000
    else:  # pcs, pack
        base = quantity / 6
    return max(0.3, base ** 0.6)


def base_price_for_product(product) -> float:
    """Deterministic base price derived from the product's own identity
    (brand+name) and category band + pack size - not random per call, so
    the *base* price for a given product is stable; platform multiplier
    and run-to-run noise (applied by the caller) are what actually vary."""
    digest = hashlib.md5(f"{product.brand}|{product.normalized_name}".encode()).hexdigest()
    fraction = int(digest[:6], 16) / 0xFFFFFF
    low, high = CATEGORY_PRICE_BANDS.get(product.category.name, _DEFAULT_BAND)
    unit_price = low + fraction * (high - low)
    return round(unit_price * _size_factor(float(product.quantity), product.unit), 2)


def _location_cost_index(locality_name: str) -> float:
    """A small, deterministic per-locality price multiplier (~0.95x-1.08x)
    simulating that some areas run slightly pricier than others."""
    digest = hashlib.md5(locality_name.encode()).hexdigest()
    fraction = int(digest[:4], 16) / 0xFFFF
    return 0.95 + fraction * 0.13


class MockScraper(BaseScraper):
    """Simulates a platform pricing engine for any canonical Product, in
    any Locality. Subclasses configure a price_multiplier, out_of_stock
    _rate, failure_rate, promotion_rate, and delivery-time range, mirroring
    how real quick-commerce apps differ from each other.

    Locality *serviceability* is NOT handled here - that's
    PlatformAvailability (see products/models.py and services.py), which
    is checked before a provider is ever called. This keeps "does this
    platform serve this area" as data, not adapter code.
    """

    price_multiplier: float = 1.0
    out_of_stock_rate: float = 0.1
    failure_rate: float = 0.0
    promotion_rate: float = 0.12
    delivery_minutes_range: tuple[int, int] = (10, 20)

    def get_offer(self, product, locality) -> ProviderOffer:
        if random.random() < self.failure_rate:
            raise ScraperError(f"{self.platform_name}: simulated network/timeout failure")

        base = base_price_for_product(product)
        location_factor = _location_cost_index(str(locality))
        fluctuation = random.uniform(-0.04, 0.04)
        price = round(base * self.price_multiplier * location_factor * (1 + fluctuation), 2)

        is_available = random.random() > self.out_of_stock_rate
        delivery_minutes = random.randint(*self.delivery_minutes_range) if is_available else None
        promotion_text = random.choice(PROMOTIONS) if is_available and random.random() < self.promotion_rate else ""

        slug = self.platform_name.lower().replace(" ", "-")
        offer = ProviderOffer(
            external_product_id=f"{slug}-{product.sku}",
            source_url=f"https://example-{slug}.demo/p/{product.sku}",
            price=price,
            is_available=is_available,
            delivery_minutes=delivery_minutes,
            promotion_text=promotion_text,
        )
        logger.info("%s (%s): %s -> \u20b9%s", self.platform_name, locality, product.name, price)
        return offer
