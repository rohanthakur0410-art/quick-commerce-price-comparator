"""
Offer materialization: turning "we haven't priced this product here yet"
into an actual ProductOffer row, and refreshing existing ones.

Architecture note (see README "How price refresh works"): with a 2000+
product catalog, pre-generating every (product, platform, locality)
combination up front would mean hundreds of thousands of rows before a
single page loads - most of which would never be viewed. Instead, offers
are materialized lazily: the first time a product is compared in a
locality, this module fetches/generates its price for every platform
that services that locality (per PlatformAvailability) and caches it as
a ProductOffer. `manage.py refresh_prices` re-materializes offers that
already exist, simulating the passage of time / a scheduled re-check.

This keeps browsing fast (a search results page only ever materializes
offers for the ~20 products actually shown) while still exercising the
full pricing pipeline for anything a user actually looks at.
"""

import logging
from decimal import Decimal, InvalidOperation

from django.utils import timezone

from .models import Platform, PlatformAvailability, PriceHistory, ProductOffer

logger = logging.getLogger("products")

#: Prices within this fraction of each other are treated as "unchanged"
#: for history-dedup purposes (see upsert_offer), to absorb rounding noise.
_UNCHANGED_TOLERANCE = Decimal("0.005")


def available_platforms_for(locality):
    """Platforms with an explicit 'available' PlatformAvailability row
    for this locality. Fail-closed: a platform with no row, or a row
    marked 'unavailable'/'unknown', is never shown here."""
    platform_ids = PlatformAvailability.objects.filter(
        locality=locality, status=PlatformAvailability.AVAILABLE
    ).values_list("platform_id", flat=True)
    return Platform.objects.filter(id__in=platform_ids, is_active=True)


def upsert_offer(product, platform, locality):
    """Call the platform's provider for (product, locality), and upsert
    the ProductOffer + (if changed) a new PriceHistory row.

    Returns (offer_or_None, error_message_or_None). Never raises -
    provider failures are reported back for the caller to log/aggregate,
    matching "continue if one platform fails" from the scrape workflow.
    """
    from scrapers.base_scraper import ScraperError
    from scrapers.registry import get_scraper_for_platform

    scraper = get_scraper_for_platform(platform.name)
    if scraper is None:
        return None, f"No provider registered for platform '{platform.name}'"

    try:
        result = scraper.get_offer(product, locality)
    except ScraperError as exc:
        return None, str(exc)

    try:
        price = Decimal(str(result.price))
    except (ValueError, TypeError, InvalidOperation):
        return None, f"Invalid price {result.price!r} from '{platform.name}'"

    offer, created = ProductOffer.objects.get_or_create(
        product=product,
        platform=platform,
        locality=locality,
        defaults={
            "external_product_id": result.external_product_id,
            "source_url": result.source_url,
            "current_price": price,
            "is_available": result.is_available,
            "delivery_minutes": result.delivery_minutes,
            "promotion_text": result.promotion_text,
            "is_demo": True,
            "last_checked_at": timezone.now(),
        },
    )

    price_changed = created or offer.current_price is None or abs(offer.current_price - price) > _UNCHANGED_TOLERANCE
    availability_changed = created or offer.is_available != result.is_available

    if not created:
        offer.external_product_id = result.external_product_id
        offer.source_url = result.source_url
        offer.current_price = price
        offer.is_available = result.is_available
        offer.delivery_minutes = result.delivery_minutes
        offer.promotion_text = result.promotion_text
        offer.last_checked_at = timezone.now()
        offer.save()

    if price_changed or availability_changed:
        PriceHistory.objects.create(
            product_offer=offer, price=price, is_available=result.is_available,
            promotion_text=result.promotion_text,
        )

    return offer, None


def ensure_offers(product, locality):
    """Materialize any missing offers for `product` in `locality`, for
    every platform that services this locality. Existing offers are left
    as-is (use refresh_offers_for to force a re-check)."""
    platforms = available_platforms_for(locality)
    existing_platform_ids = set(
        ProductOffer.objects.filter(product=product, locality=locality).values_list("platform_id", flat=True)
    )
    errors = []
    for platform in platforms:
        if platform.id in existing_platform_ids:
            continue
        _, error = upsert_offer(product, platform, locality)
        if error:
            errors.append((platform.name, error))
            logger.info("Could not price '%s' on %s in %s: %s", product.name, platform.name, locality, error)
    return errors


def refresh_offers_for(product, locality):
    """Re-materialize offers for every platform servicing this locality,
    regardless of whether one already exists - the 'time has passed,
    check again' operation used by manage.py refresh_prices."""
    platforms = available_platforms_for(locality)
    touched = 0
    errors = []
    for platform in platforms:
        offer, error = upsert_offer(product, platform, locality)
        if error:
            errors.append((platform.name, error))
        else:
            touched += 1
    return touched, errors
