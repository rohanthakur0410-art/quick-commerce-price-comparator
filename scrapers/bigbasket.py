"""Demo adapter for BigBasket / BB Now. See mock_scraper.py / blinkit.py
for why this is simulated rather than a live scraper.

BigBasket's coverage gaps (real quick-delivery formats don't cover every
town) are represented as data via PlatformAvailability, not hard-coded
here - see products/management/commands/seed_data.py.
"""

from .mock_scraper import MockScraper


class BigBasketScraper(MockScraper):
    platform_name = "BigBasket"
    price_multiplier = 1.06
    out_of_stock_rate = 0.16
    failure_rate = 0.04
    promotion_rate = 0.09
    delivery_minutes_range = (18, 28)
