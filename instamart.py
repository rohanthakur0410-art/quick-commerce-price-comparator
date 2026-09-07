"""Demo adapter for Swiggy Instamart. See mock_scraper.py / blinkit.py
for why this is simulated rather than a live scraper."""

from .mock_scraper import MockScraper


class InstamartScraper(MockScraper):
    platform_name = "Swiggy Instamart"
    price_multiplier = 1.04
    out_of_stock_rate = 0.12
    failure_rate = 0.03
    promotion_rate = 0.10
    delivery_minutes_range = (14, 22)
