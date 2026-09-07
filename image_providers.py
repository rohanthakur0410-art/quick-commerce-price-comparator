"""
Pluggable image providers for products.

Product.image_path is the single source of truth for what's displayed
(see products/imaging.py for the on-disk placeholder generator this
module builds on) - this file adds a provider abstraction so a real
photo source can be swapped in without touching any template or view.

IMPORTANT / honest limitation of this deployment: this sandboxed build
environment's outbound network access is restricted to package
registries (pip/npm/etc.) - it cannot reach general image/API hosts.
RemoteImageProvider below is implemented correctly and is the intended
production path (see its docstring for the real, openly-licensed API it
targets and how it's used), but it has NOT been exercised against a live
network from here, and `fetch_product_images` (the command that uses it)
is not run as part of this project's automated seeding. The active
provider in this repository's default configuration remains
PlaceholderProvider - every product always has a real, working image
file; nothing is ever a broken-image icon.
"""

import logging
from abc import ABC, abstractmethod
from typing import Optional

logger = logging.getLogger("products")


class ImageProvider(ABC):
    """Given a product, return a *local, static-served* relative path
    for its image, or None if this provider can't supply one (the
    caller should then fall back to the next provider / the
    placeholder). Providers are responsible for their own caching -
    get_image_path() should be safe to call repeatedly without
    re-fetching anything already on disk.
    """

    @abstractmethod
    def get_image_path(self, product) -> Optional[str]:
        raise NotImplementedError


class PlaceholderProvider(ImageProvider):
    """Wraps the existing SVG placeholder generator (products/imaging.py).
    Always succeeds - this is the guaranteed fallback, never a broken
    image."""

    def get_image_path(self, product) -> Optional[str]:
        from .imaging import ensure_product_image
        ensure_product_image(product)
        return product.image_path or None


class RemoteImageProvider(ImageProvider):
    """Fetches a real product photo from Open Food Facts
    (https://world.openfoodfacts.org), an open, crowd-sourced grocery
    -product database (data under ODbL, images under CC-BY-SA) that
    explicitly documents and permits this kind of programmatic use, with
    a clear User-Agent identifying the caller as their terms request.

    Looks the product up by brand + name via their public search API,
    downloads the front-of-pack image if a match is found, and caches it
    to static/product_images/remote/<sku>.<ext> - so, like the
    placeholder path, an already-fetched image is never re-downloaded.

    Every network call has an explicit timeout and is wrapped so a
    failure (timeout, no match, non-200, malformed response) simply
    returns None - callers fall back to PlaceholderProvider, never a
    broken image or a crashed request.
    """

    SEARCH_URL = "https://world.openfoodfacts.org/cgi/search.pl"
    TIMEOUT_SECONDS = 6
    USER_AGENT = "QuickCart-PriceComparator/1.0 (portfolio project; contact: none)"

    def get_image_path(self, product) -> Optional[str]:
        import os

        from django.conf import settings

        cache_dir = settings.BASE_DIR / "static" / "product_images" / "remote"
        # Reuse a cached download if we already have one for this SKU,
        # regardless of extension.
        if cache_dir.exists():
            for existing in cache_dir.glob(f"{product.sku}.*"):
                return f"product_images/remote/{existing.name}"

        image_url = self._search_image_url(product)
        if not image_url:
            return None

        local_path = self._download(image_url, product.sku, cache_dir)
        if local_path is None:
            return None

        os.makedirs(cache_dir, exist_ok=True)
        return f"product_images/remote/{local_path.name}"

    def _search_image_url(self, product) -> Optional[str]:
        import requests

        query = f"{product.brand} {product.name}"
        try:
            response = requests.get(
                self.SEARCH_URL,
                params={"search_terms": query, "json": 1, "page_size": 1},
                headers={"User-Agent": self.USER_AGENT},
                timeout=self.TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            data = response.json()
        except (requests.RequestException, ValueError) as exc:
            logger.info("RemoteImageProvider: search failed for %r: %s", query, exc)
            return None

        products = data.get("products") or []
        if not products:
            return None
        return products[0].get("image_front_small_url") or products[0].get("image_url")

    def _download(self, image_url: str, sku: str, cache_dir):
        import requests

        try:
            response = requests.get(image_url, headers={"User-Agent": self.USER_AGENT}, timeout=self.TIMEOUT_SECONDS)
            response.raise_for_status()
        except requests.RequestException as exc:
            logger.info("RemoteImageProvider: download failed for %s: %s", image_url, exc)
            return None

        ext = ".jpg"
        for candidate in (".jpg", ".jpeg", ".png", ".webp"):
            if image_url.lower().split("?")[0].endswith(candidate):
                ext = candidate
                break

        import os
        os.makedirs(cache_dir, exist_ok=True)
        local_path = cache_dir / f"{sku}{ext}"
        local_path.write_bytes(response.content)
        return local_path


def get_active_providers() -> list:
    """Providers tried in order for `fetch_product_images`
    (RemoteImageProvider first, PlaceholderProvider as the guaranteed
    fallback). Kept as a function (not a module-level constant) so tests
    can substitute providers without monkeypatching internals."""
    return [RemoteImageProvider(), PlaceholderProvider()]
