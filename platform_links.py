"""
Builds the "Buy on <Platform>" redirect URL for an offer.

We have no real per-product platform URLs (every ProductOffer in this
project is simulated - see README "Demo vs Live data"), so every link
here goes to the platform's real, live website - either a verified search
results page for the product name, or (where a search URL pattern
couldn't be confirmed) the platform's homepage. Never a fabricated
per-product URL, and never presented as more precise than it is.

Search-URL patterns below were verified against real usage (platform
scraper docs / public examples) rather than guessed:
  - Blinkit:  https://blinkit.com/s/?q=<query>
  - Zepto:    https://www.zeptonow.com/search?query=<query>
  - Flipkart: https://www.flipkart.com/search?q=<query>  (Flipkart's
    general site search - reliably documented; not confirmed to deep
    -link into the "Minutes" quick-commerce section specifically).

Swiggy Instamart and BigBasket don't have a publicly confirmed direct
search-URL pattern (both are heavily session/location-gated SPAs), so
those fall back to the platform's real homepage (Platform.base_url)
rather than a guessed query string that might silently not work.
"""

from urllib.parse import quote_plus

_SEARCH_URL_BUILDERS = {
    "blinkit": lambda query: f"https://blinkit.com/s/?q={quote_plus(query)}",
    "zepto": lambda query: f"https://www.zeptonow.com/search?query={quote_plus(query)}",
    "flipkart-minutes": lambda query: f"https://www.flipkart.com/search?q={quote_plus(query)}",
}


def build_platform_link(platform, product_name: str) -> dict:
    """Returns {"url": str, "is_search": bool} for a platform + product
    name. is_search=True means the URL is a search-results page for the
    product name, not a specific product page (we don't have those) -
    templates should label the button accordingly rather than implying
    more precision than the link actually has.
    """
    builder = _SEARCH_URL_BUILDERS.get(platform.slug)
    if builder:
        return {"url": builder(product_name), "is_search": True}
    if platform.base_url:
        return {"url": platform.base_url, "is_search": False}
    return {"url": "", "is_search": False}
