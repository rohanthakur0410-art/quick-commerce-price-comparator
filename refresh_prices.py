"""
Management command: python manage.py refresh_prices [--locality "Koramangala, Bengaluru"] [--warm N]

Re-checks prices for ProductOffer rows that already exist (i.e. products
someone has actually viewed/searched, per the lazy-materialization
architecture - see products/pricing.py), simulating a scheduled
re-check. Running this repeatedly produces realistic price drift: each
run nudges prices by a small bounded amount per platform/locality,
occasionally flips availability/promotions, and PriceHistory grows only
where something actually changed.

--warm N pre-materializes offers for N products that don't have any yet,
in the given (or a default) locality - useful for demoing/testing
refresh behavior without having to browse the site first.
"""

import logging
import random

from django.core.management.base import BaseCommand, CommandError

from products.models import Locality, Product, ProductOffer
from products.pricing import ensure_offers, refresh_offers_for

logger = logging.getLogger("products")


class Command(BaseCommand):
    help = "Re-check prices for already-materialized product offers, simulating scheduled price checks."

    def add_arguments(self, parser):
        parser.add_argument("--locality", type=str, default=None, help="Restrict to one locality, e.g. 'Koramangala'.")
        parser.add_argument("--warm", type=int, default=0, help="Materialize offers for N un-priced products first.")

    def handle(self, *args, **options):
        locality_filter = options.get("locality")
        warm_count = options.get("warm") or 0

        localities = Locality.objects.filter(is_active=True)
        if locality_filter:
            localities = localities.filter(name__icontains=locality_filter)
            if not localities.exists():
                raise CommandError(f"No active locality matching '{locality_filter}'.")

        if warm_count:
            for locality in localities:
                unpriced = Product.objects.filter(is_active=True).exclude(
                    offers__locality=locality
                )[:warm_count]
                for product in unpriced:
                    ensure_offers(product, locality)
                self.stdout.write(f"Warmed up to {warm_count} product(s) in {locality}.")

        total_touched = 0
        total_errors = 0
        for locality in localities:
            products = Product.objects.filter(offers__locality=locality).distinct()
            for product in products:
                touched, errors = refresh_offers_for(product, locality)
                total_touched += touched
                total_errors += len(errors)
                for platform_name, error in errors:
                    self.stdout.write(f"  [!] {platform_name} ({locality}) - {product.name}: {error}")

            self.stdout.write(f"{locality}: refreshed offers for {products.count()} product(s).")

        self.stdout.write(self.style.SUCCESS(
            f"Done. {total_touched} offer check(s) completed, {total_errors} failed/unavailable."
        ))
