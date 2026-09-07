"""Demo adapter for Blinkit. See mock_scraper.py for why this is
simulated rather than a live scraper."""

from .mock_scraper import MockScraper


class BlinkitScraper(MockScraper):
    platform_name = "Blinkit"
    price_multiplier = 1.0
    out_of_stock_rate = 0.08
    failure_rate = 0.02
    promotion_rate = 0.14
    delivery_minutes_range = (8, 15)
