"""
Common interface every platform provider implements.

This is the abstraction that lets the comparison engine stay completely
ignorant of HTML scraping, APIs, or anti-bot handling: it asks a provider
"price this canonical product, in this locality" and gets back a
standardized ProviderOffer. Adding a new platform is one new class
implementing BaseScraper, registered in scrapers/registry.py - nothing
in products/services.py or the views change.

Design note vs. the conceptual interface (search_products, get_price,
get_availability, get_source_url, get_promotion, refresh_offers): those
are consolidated here into one call, get_offer(), which returns all of
price/availability/delivery/promotion/source_url together. Product
*search* isn't a provider concern in this architecture - the canonical
catalog lives in the database (see products/models.py Product), so
search is a Product query (products/api_views.py, products/views.py),
not per-platform text matching. Consolidating the rest into one call
avoids issuing 4-5 separate "queries" per platform per product, which
would multiply badly at catalog scale (see README "Performance").
refresh_offers is just this same call, invoked again later - there's no
separate code path for "first check" vs. "refresh".
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class ProviderOffer:
    """A single price/availability observation for one product, on one
    platform, in one locality."""

    external_product_id: str
    source_url: str
    price: float
    is_available: bool
    delivery_minutes: Optional[int] = None
    promotion_text: str = ""


class ScraperError(Exception):
    """Raised when a provider cannot price a product in a locality
    (simulated network error, platform doesn't service the area, etc).
    Callers treat this as "this platform failed for this product/
    locality", not a reason to abort the whole run.
    """


class BaseScraper(ABC):
    """Interface every platform provider implements."""

    #: Human-readable platform name. Must match a Platform.name in the DB.
    platform_name: str = "Unknown Platform"

    @abstractmethod
    def get_offer(self, product, locality) -> ProviderOffer:
        """Price `product` (a products.models.Product) in `locality` (a
        products.models.Locality) and return a ProviderOffer.

        Implementations should raise ScraperError (not let arbitrary
        exceptions propagate) if the product can't be priced there, so
        callers can log the failure and move on.
        """
        raise NotImplementedError

    def refresh_offers(self, product, locality) -> ProviderOffer:
        """Alias for get_offer() - the management command's "refresh"
        step is exactly the same operation as the first check."""
        return self.get_offer(product, locality)
