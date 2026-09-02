from django.test import TestCase

from products.normalization import dedup_key, generate_sku, normalize_product_name, parse_size


class NormalizeProductNameTests(TestCase):
    def test_strips_size_and_punctuation(self):
        self.assertEqual(normalize_product_name("Amul Taaza Milk - 1L"), "amul taaza milk")
        self.assertEqual(normalize_product_name("Amul Taaza Toned Milk 1 L"), "amul taaza toned milk")

    def test_case_insensitive(self):
        self.assertEqual(normalize_product_name("MAGGI NOODLES"), normalize_product_name("maggi noodles"))

    def test_collapses_whitespace(self):
        self.assertEqual(normalize_product_name("Tata   Salt"), "tata salt")

    def test_empty_input(self):
        self.assertEqual(normalize_product_name(""), "")
        self.assertEqual(normalize_product_name(None), "")


class ParseSizeTests(TestCase):
    def test_parses_common_units(self):
        self.assertEqual(parse_size("1kg"), ("1", "kg"))
        self.assertEqual(parse_size("500 ml"), ("500", "ml"))
        self.assertEqual(parse_size("6 pcs"), ("6", "pcs"))
        self.assertEqual(parse_size("1.25L"), ("1.25", "l"))

    def test_unparseable_returns_none(self):
        self.assertEqual(parse_size("large"), (None, None))
        self.assertEqual(parse_size(""), (None, None))


class DedupKeyTests(TestCase):
    def test_key_is_case_insensitive_on_brand(self):
        k1 = dedup_key("Amul", "taaza milk", "1", "l")
        k2 = dedup_key("amul", "taaza milk", "1", "l")
        self.assertEqual(k1, k2)

    def test_different_quantity_gives_different_key(self):
        k1 = dedup_key("Amul", "taaza milk", "1", "l")
        k2 = dedup_key("Amul", "taaza milk", "0.5", "l")
        self.assertNotEqual(k1, k2)

    def test_different_unit_gives_different_key(self):
        k1 = dedup_key("Local", "rice", "1", "kg")
        k2 = dedup_key("Local", "rice", "1", "l")
        self.assertNotEqual(k1, k2)


class GenerateSkuTests(TestCase):
    def test_generates_slug_like_string(self):
        sku = generate_sku("Amul", "Taaza Milk", "1", "l")
        self.assertTrue(sku.replace("-", "").isalnum())
        self.assertIn("amul", sku)
