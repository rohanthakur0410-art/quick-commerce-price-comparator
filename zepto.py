"""Demo adapter for Zepto. See mock_scraper.py / blinkit.py for why this
is simulated rather than a live scraper."""

from .mock_scraper import MockScraper


class ZeptoScraper(MockScraper):
    platform_name = "Zepto"
    price_multiplier = 0.98
    out_of_stock_rate = 0.10
    failure_rate = 0.02
    promotion_rate = 0.12
    delivery_minutes_range = (7, 14)
