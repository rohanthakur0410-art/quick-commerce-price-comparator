"""
Maps Platform names (as stored in the DB) to their provider
implementation.

To add a new platform:
  1. Write a new adapter class implementing BaseScraper (see blinkit.py).
  2. Add an entry to SCRAPER_REGISTRY below.
  3. Create a matching Platform row (via admin or seed_data), and
     PlatformAvailability rows for the localities it serves.

Nothing else in the app needs to change - the comparison engine and
management commands work off this registry and the Platform/
PlatformAvailability tables, never hard-coded platform names.
"""

from .bigbasket import BigBasketScraper
from .blinkit import BlinkitScraper
from .flipkart_minutes import FlipkartMinutesScraper
from .instamart import InstamartScraper
from .zepto import ZeptoScraper

SCRAPER_REGISTRY = {
    "Blinkit": BlinkitScraper,
    "Zepto": ZeptoScraper,
    "Swiggy Instamart": InstamartScraper,
    "Flipkart Minutes": FlipkartMinutesScraper,
    "BigBasket": BigBasketScraper,
}


def get_scraper_for_platform(platform_name: str):
    scraper_class = SCRAPER_REGISTRY.get(platform_name)
    return scraper_class() if scraper_class else None
