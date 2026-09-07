"""
Management command: python manage.py generate_product_images

Generates a placeholder image for every active product that doesn't
already have one (products/imaging.py), and caches the path on
Product.image_path. Safe to re-run - already-imaged products are
skipped, and no other product data is touched.
"""

from django.core.management.base import BaseCommand

from products.imaging import ensure_product_image
from products.models import Product


class Command(BaseCommand):
    help = "Generate placeholder images for products that don't have one yet."

    def handle(self, *args, **options):
        products = Product.objects.filter(is_active=True).select_related("subcategory__category")
        generated = 0
        already_had = 0
        for product in products:
            if product.image_path:
                already_had += 1
                continue
            ensure_product_image(product)
            generated += 1

        self.stdout.write(self.style.SUCCESS(
            f"Generated {generated} image(s); {already_had} product(s) already had one."
        ))
