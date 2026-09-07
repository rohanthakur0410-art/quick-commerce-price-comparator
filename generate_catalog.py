"""
Management command: python manage.py generate_catalog --out fixtures/generated_products.json

Expands products/taxonomy.py's brand x variant x size templates into a
flat JSON file of individual product records, ready for
`manage.py import_products`. This is the "structured external data +
reusable generation logic" the catalog is built from, rather than a
2000-line hand-written product list.
"""

import json

from django.core.management.base import BaseCommand

from products.taxonomy import TEMPLATES


def _build_name(brand, variant, base_name, size):
    parts = [p for p in [brand, variant, base_name] if p]
    return f"{' '.join(parts)} {size}".strip()


class Command(BaseCommand):
    help = "Generate a realistic demo product catalog (JSON) from products/taxonomy.py templates."

    def add_arguments(self, parser):
        parser.add_argument("--out", type=str, default="fixtures/generated_products.json")

    def handle(self, *args, **options):
        out_path = options["out"]
        records = []
        for template in TEMPLATES:
            for brand in template["brands"]:
                for variant in template["variants"]:
                    for size in template["sizes"]:
                        records.append({
                            "name": _build_name(brand, variant, template["base_name"], size),
                            "brand": brand,
                            "category": template["category"],
                            "subcategory": template["subcategory"],
                            "size": size,
                        })

        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(records, f, indent=2)

        self.stdout.write(self.style.SUCCESS(f"Generated {len(records)} product record(s) -> {out_path}"))
        self.stdout.write("Run 'python manage.py import_products " + out_path + "' to load them.")
