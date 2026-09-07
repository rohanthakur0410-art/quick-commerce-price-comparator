"""
Management command: python manage.py fetch_product_images [--limit N] [--only-missing-real]

Enriches products with a real photo where one can be found (via
RemoteImageProvider - see products/image_providers.py), falling back to
the existing SVG placeholder per-product on any failure. Deliberately
SEPARATE from seed_data/generate_product_images: this makes real network
requests and must never run implicitly at seed time (see README
"Seed data vs. image enrichment").

This is a batch job, not a request-time fetch - product pages never
depend on an external image request; they only ever read the cached
Product.image_path set here (or by generate_product_images).

Note: in a network-restricted environment (no route to
world.openfoodfacts.org), every lookup will fail closed and every
product will keep/receive its placeholder - safe, but real images won't
actually populate. See README for details.
"""

from django.core.management.base import BaseCommand

from products.image_providers import get_active_providers
from products.models import Product


class Command(BaseCommand):
    help = "Fetch real product images where available, falling back to placeholders. Separate from seed_data - makes network requests."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=200, help="Max number of products to process in this run (batched, resumable).")

    def handle(self, *args, **options):
        limit = options["limit"]
        providers = get_active_providers()

        # Only products still on a placeholder (or with no image at all)
        # are candidates - already-fetched real images are never re-requested.
        candidates = Product.objects.filter(is_active=True).exclude(
            image_path__startswith="product_images/remote/"
        )[:limit]

        fetched_real = 0
        fell_back = 0
        for product in candidates:
            for provider in providers:
                path = provider.get_image_path(product)
                if path:
                    if product.image_path != path:
                        product.image_path = path
                        product.save(update_fields=["image_path"])
                    if path.startswith("product_images/remote/"):
                        fetched_real += 1
                    else:
                        fell_back += 1
                    break

        self.stdout.write(self.style.SUCCESS(
            f"Processed {candidates.count()} product(s): {fetched_real} real image(s) fetched, "
            f"{fell_back} fell back to placeholder. Run again with --limit to process more."
        ))
