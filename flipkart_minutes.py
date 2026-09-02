"""Demo adapter for Flipkart Minutes. See mock_scraper.py / blinkit.py
for why this is simulated rather than a live scraper."""

from .mock_scraper import MockScraper


class FlipkartMinutesScraper(MockScraper):
    platform_name = "Flipkart Minutes"
    price_multiplier = 1.02
    out_of_stock_rate = 0.14
    failure_rate = 0.03
    promotion_rate = 0.10
    delivery_minutes_range = (13, 21)
