"""
Management command: python manage.py import_products <file.json|file.csv> [--dry-run]

Idempotent product ingestion. Reads external product data (JSON list of
objects, or CSV with the same columns), validates it, normalizes each
record's name, matches it against existing canonical products (brand +
normalized_name + quantity + unit - see products/normalization.py), and
creates or updates Product rows accordingly. Running the same file twice
produces the same end state (0 newly created the second time) - see
products/tests/test_ingestion.py.

Expected fields per record:
    name        (required)
    brand       (required)
    category    (required - top-level Category name)
    subcategory (required - Subcategory name under that category)
    sku         (optional - generated if omitted)
  and either:
    quantity + unit   (unit must be one of products.models.UNIT_CHOICES)
  or:
    size        (e.g. "1kg", "500 ml" - parsed by normalization.parse_size)
"""

import csv
import json

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from products.models import UNIT_CHOICES, Category, Product, Subcategory
from products.normalization import dedup_key, generate_sku, normalize_product_name, parse_size

VALID_UNITS = {code for code, _ in UNIT_CHOICES}


def _load_records(file_path):
    if file_path.endswith(".json"):
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    if file_path.endswith(".csv"):
        with open(file_path, "r", encoding="utf-8") as f:
            return list(csv.DictReader(f))
    raise CommandError(f"Unsupported file type: {file_path} (expected .json or .csv)")


def _validate_and_normalize(row):
    """Returns (clean_record_dict, error_reason_or_None)."""
    name = (row.get("name") or "").strip()
    brand = (row.get("brand") or "").strip()
    category = (row.get("category") or "").strip()
    subcategory = (row.get("subcategory") or "").strip()

    if not name or not brand or not category or not subcategory:
        return None, "missing required field (name/brand/category/subcategory)"

    quantity = row.get("quantity")
    unit = (row.get("unit") or "").strip().lower() or None
    if quantity is None or unit is None:
        quantity, unit = parse_size(row.get("size", ""))

    if quantity is None or unit not in VALID_UNITS:
        return None, f"unparseable or invalid quantity/unit ({row.get('quantity')!r}/{row.get('unit')!r}/{row.get('size')!r})"

    try:
        quantity = round(float(quantity), 3)
        if quantity <= 0:
            return None, "quantity must be positive"
    except (TypeError, ValueError):
        return None, f"invalid quantity {quantity!r}"

    return {
        "name": name, "brand": brand, "category": category, "subcategory": subcategory,
        "quantity": quantity, "unit": unit, "sku": (row.get("sku") or "").strip(),
    }, None


class Command(BaseCommand):
    help = "Idempotently import canonical products from a JSON or CSV file, in batches (so very large files don't sit in one giant transaction)."

    def add_arguments(self, parser):
        parser.add_argument("file_path", type=str)
        parser.add_argument("--dry-run", action="store_true", help="Report what would happen without writing to the database.")
        parser.add_argument("--batch-size", type=int, default=5000,
                             help="Commit every N records (default 5000). Keeps memory/lock time bounded on very large files "
                                  "instead of one all-or-nothing transaction - see README 'Scaling to 3 crore+ products'.")
        parser.add_argument("--offset", type=int, default=0, help="Skip the first N records - resume a partial import.")
        parser.add_argument("--limit", type=int, default=None, help="Stop after N records (from --offset) - process a file in chunks across multiple runs.")

    def handle(self, *args, **options):
        file_path = options["file_path"]
        dry_run = options["dry_run"]
        batch_size = options["batch_size"]
        records = _load_records(file_path)

        offset = options["offset"]
        limit = options["limit"]
        records = records[offset:offset + limit] if limit is not None else records[offset:]

        stats = {"created": 0, "updated": 0, "skipped": 0, "invalid": 0, "duplicate": 0}
        invalid_examples = []
        seen_keys = set()

        def process_batch(batch):
            for row in batch:
                clean, error = _validate_and_normalize(row)
                if error:
                    stats["invalid"] += 1
                    if len(invalid_examples) < 10:
                        invalid_examples.append(f"{row.get('name', '<no name>')!r}: {error}")
                    continue

                normalized = normalize_product_name(clean["name"])
                key = dedup_key(clean["brand"], normalized, clean["quantity"], clean["unit"])
                if key in seen_keys:
                    stats["duplicate"] += 1
                    continue
                seen_keys.add(key)

                category_obj, _ = Category.objects.get_or_create(name=clean["category"])
                subcategory_obj, _ = Subcategory.objects.get_or_create(category=category_obj, name=clean["subcategory"])

                existing = Product.objects.filter(
                    brand__iexact=clean["brand"], normalized_name=normalized,
                    quantity=clean["quantity"], unit=clean["unit"],
                ).first()

                if existing:
                    changed = False
                    if existing.name != clean["name"]:
                        existing.name = clean["name"]
                        changed = True
                    if existing.subcategory_id != subcategory_obj.id:
                        existing.subcategory = subcategory_obj
                        changed = True
                    if changed:
                        existing.save()
                        stats["updated"] += 1
                    else:
                        stats["skipped"] += 1
                else:
                    sku = clean["sku"] or generate_sku(clean["brand"], clean["name"], clean["quantity"], clean["unit"])
                    if Product.objects.filter(sku=sku).exists():
                        sku = f"{sku}-{Product.objects.count() + 1}"
                    Product.objects.create(
                        name=clean["name"], brand=clean["brand"], subcategory=subcategory_obj,
                        quantity=clean["quantity"], unit=clean["unit"], sku=sku,
                    )
                    stats["created"] += 1

        if dry_run:
            # A preview doesn't need batched commits - one transaction,
            # rolled back at the end, is simpler and just as correct.
            with transaction.atomic():
                process_batch(records)
                transaction.set_rollback(True)
        else:
            for start in range(0, len(records), batch_size):
                with transaction.atomic():
                    process_batch(records[start:start + batch_size])

        self.stdout.write(
            f"{'[DRY RUN] ' if dry_run else ''}created={stats['created']} updated={stats['updated']} "
            f"skipped={stats['skipped']} duplicate={stats['duplicate']} invalid={stats['invalid']}"
        )
        for example in invalid_examples:
            self.stdout.write(self.style.WARNING(f"  invalid: {example}"))
        self.stdout.write(self.style.SUCCESS("Import complete." if not dry_run else "Dry run complete - no changes written."))
