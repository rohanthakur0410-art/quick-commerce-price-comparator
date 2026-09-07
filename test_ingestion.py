import json
import tempfile
from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from products.models import Category, Product, Subcategory


def _write_json(records):
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
    json.dump(records, f)
    f.close()
    return f.name


class ImportProductsTests(TestCase):
    def _import(self, path, dry_run=False):
        out = StringIO()
        args = [path]
        if dry_run:
            args.append("--dry-run")
        call_command("import_products", *args, stdout=out)
        return out.getvalue()

    def test_creates_new_products(self):
        path = _write_json([
            {"name": "Amul Taaza Milk 1L", "brand": "Amul", "category": "Dairy", "subcategory": "Milk", "size": "1L"},
            {"name": "Maggi Noodles 70g", "brand": "Nestle", "category": "Snacks", "subcategory": "Instant Noodles", "size": "70g"},
        ])
        output = self._import(path)
        self.assertIn("created=2", output)
        self.assertEqual(Product.objects.count(), 2)

    def test_idempotent_reimport_creates_nothing(self):
        path = _write_json([
            {"name": "Tata Salt 1kg", "brand": "Tata", "category": "Grocery", "subcategory": "Salt", "size": "1kg"},
        ])
        self._import(path)
        output = self._import(path)
        self.assertIn("created=0", output)
        self.assertIn("skipped=1", output)
        self.assertEqual(Product.objects.count(), 1)

    def test_duplicate_within_same_file_counted_separately(self):
        path = _write_json([
            {"name": "Dove Soap 100g", "brand": "Dove", "category": "Personal Care", "subcategory": "Bath & Body", "size": "100g"},
            {"name": "Dove Soap 100g", "brand": "Dove", "category": "Personal Care", "subcategory": "Bath & Body", "size": "100g"},
        ])
        output = self._import(path)
        self.assertIn("created=1", output)
        self.assertIn("duplicate=1", output)
        self.assertEqual(Product.objects.count(), 1)

    def test_invalid_record_is_skipped_not_fatal(self):
        path = _write_json([
            {"name": "", "brand": "Amul", "category": "Dairy", "subcategory": "Milk", "size": "1L"},
            {"name": "Valid Product", "brand": "Brand", "category": "Grocery", "subcategory": "Rice", "size": "1kg"},
            {"name": "Bad Size Product", "brand": "Brand", "category": "Grocery", "subcategory": "Rice", "size": "huge"},
        ])
        output = self._import(path)
        self.assertIn("created=1", output)
        self.assertIn("invalid=2", output)
        self.assertEqual(Product.objects.count(), 1)

    def test_dry_run_writes_nothing(self):
        path = _write_json([
            {"name": "Test Product", "brand": "Brand", "category": "Grocery", "subcategory": "Rice", "size": "1kg"},
        ])
        output = self._import(path, dry_run=True)
        self.assertIn("[DRY RUN]", output)
        self.assertIn("created=1", output)
        self.assertEqual(Product.objects.count(), 0)
        self.assertEqual(Category.objects.count(), 0)

    def test_updates_existing_when_name_formatting_changes(self):
        # Same canonical product (brand+normalized_name+qty+unit all
        # match) with different raw text/punctuation -> update, not a
        # new product. A genuinely different descriptive name changes
        # normalized_name and is correctly treated as a different
        # product (see test_ingestion for the dedup-key rationale).
        path1 = _write_json([{"name": "Amul Taaza Milk 1L", "brand": "Amul", "category": "Dairy", "subcategory": "Milk", "size": "1L"}])
        self._import(path1)
        path2 = _write_json([{"name": "Amul Taaza Milk - 1 L", "brand": "Amul", "category": "Dairy", "subcategory": "Milk", "size": "1L"}])
        output = self._import(path2)
        self.assertIn("updated=1", output)
        self.assertEqual(Product.objects.count(), 1)
        self.assertEqual(Product.objects.first().name, "Amul Taaza Milk - 1 L")

    def test_creates_category_and_subcategory(self):
        path = _write_json([{"name": "New Category Item 1kg", "brand": "Brand", "category": "Brand New Category", "subcategory": "Brand New Sub", "size": "1kg"}])
        self._import(path)
        self.assertTrue(Category.objects.filter(name="Brand New Category").exists())
        self.assertTrue(Subcategory.objects.filter(name="Brand New Sub", category__name="Brand New Category").exists())

    def test_batch_offset_limit_allow_resumable_import(self):
        path = _write_json([
            {"name": "Product A 1kg", "brand": "BrandA", "category": "Grocery", "subcategory": "Rice", "size": "1kg"},
            {"name": "Product B 1kg", "brand": "BrandB", "category": "Grocery", "subcategory": "Rice", "size": "1kg"},
            {"name": "Product C 1kg", "brand": "BrandC", "category": "Grocery", "subcategory": "Rice", "size": "1kg"},
        ])
        out1 = StringIO()
        call_command("import_products", path, "--offset", "0", "--limit", "2", stdout=out1)
        self.assertIn("created=2", out1.getvalue())
        self.assertEqual(Product.objects.count(), 2)

        out2 = StringIO()
        call_command("import_products", path, "--offset", "2", "--limit", "1", stdout=out2)
        self.assertIn("created=1", out2.getvalue())
        self.assertEqual(Product.objects.count(), 3)

    def test_small_batch_size_still_imports_everything(self):
        path = _write_json([
            {"name": f"Batch Test Product {i} 1kg", "brand": "BatchBrand", "category": "Grocery", "subcategory": "Rice", "size": "1kg"}
            for i in range(5)
        ])
        output = StringIO()
        call_command("import_products", path, "--batch-size", "2", stdout=output)
        self.assertIn("created=5", output.getvalue())
        self.assertEqual(Product.objects.count(), 5)


    def test_generates_at_least_2000_records(self):
        from products.taxonomy import expected_product_count
        self.assertGreaterEqual(expected_product_count(), 2000)

    def test_generate_catalog_command_writes_expected_count(self):
        out_path = tempfile.NamedTemporaryFile(suffix=".json", delete=False).name
        call_command("generate_catalog", out=out_path)
        with open(out_path) as f:
            records = json.load(f)
        from products.taxonomy import expected_product_count
        self.assertEqual(len(records), expected_product_count())
        self.assertGreaterEqual(len(records), 2000)

    def test_generated_records_are_realistic_not_placeholders(self):
        out_path = tempfile.NamedTemporaryFile(suffix=".json", delete=False).name
        call_command("generate_catalog", out=out_path)
        with open(out_path) as f:
            records = json.load(f)
        names = [r["name"] for r in records]
        self.assertFalse(any(n.lower().startswith("product ") for n in names))
        self.assertTrue(any("Amul" in n for n in names))
        self.assertTrue(any("Maggi" in n for n in names))
