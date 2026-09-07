from decimal import Decimal

from django.test import TestCase

from products.imaging import ensure_product_image, generate_placeholder_svg, image_relative_path_for
from products.models import Category, Platform, Product, Subcategory
from products.platform_links import build_platform_link


class PlaceholderImageTests(TestCase):
    def setUp(self):
        # Distinctive brand/name so generated files can never collide
        # with a real product's already-generated image on disk (the
        # static/ directory persists across test runs, unlike the DB).
        category = Category.objects.create(name="Snacks & Packaged Food")
        subcategory = Subcategory.objects.create(name="Chips", category=category)
        self.product = Product.objects.create(
            name="Zzztestbrand Salted Chips 52g", brand="Zzztestbrand", subcategory=subcategory,
            quantity=Decimal("52.000"), unit="g",
        )

    def tearDown(self):
        from django.conf import settings
        if self.product.image_path:
            file_path = settings.BASE_DIR / "static" / self.product.image_path
            file_path.unlink(missing_ok=True)

    def test_svg_contains_brand_initial_and_category(self):
        svg = generate_placeholder_svg(self.product)
        self.assertIn("<svg", svg)
        self.assertIn("Z", svg)  # Zzztestbrand -> "Z"
        self.assertIn("Snacks &amp; Packaged Food", svg)

    def test_svg_escapes_special_characters(self):
        category = Category.objects.create(name="Test & <Category>")
        subcategory = Subcategory.objects.create(name="Sub", category=category)
        product = Product.objects.create(
            name="Weird Product", brand="A&B", subcategory=subcategory, quantity=Decimal("1.000"), unit="kg"
        )
        svg = generate_placeholder_svg(product)
        self.assertNotIn("<Category>", svg)  # must be escaped, not raw
        self.assertIn("&amp;", svg)

    def test_ensure_product_image_sets_path_and_writes_file(self):
        self.assertEqual(self.product.image_path, "")
        generated = ensure_product_image(self.product)
        self.assertTrue(generated)
        self.product.refresh_from_db()
        self.assertEqual(self.product.image_path, image_relative_path_for(self.product))

        from django.conf import settings
        file_path = settings.BASE_DIR / "static" / self.product.image_path
        self.assertTrue(file_path.exists())

    def test_ensure_product_image_is_idempotent(self):
        ensure_product_image(self.product)
        first_path = self.product.image_path
        generated_again = ensure_product_image(self.product)
        self.assertFalse(generated_again)  # file already existed, not regenerated
        self.assertEqual(self.product.image_path, first_path)

    def test_size_label_has_no_trailing_zeros(self):
        # Decimal('52.000') should render as "52g", not "52.000g".
        svg = generate_placeholder_svg(self.product)
        self.assertIn("52g", svg)
        self.assertNotIn("52.000g", svg)


class PlatformLinkTests(TestCase):
    def test_blinkit_uses_verified_search_url(self):
        platform = Platform.objects.create(name="Blinkit", slug="blinkit", base_url="https://blinkit.com")
        link = build_platform_link(platform, "Amul Taaza Milk 1L")
        self.assertTrue(link["url"].startswith("https://blinkit.com/s/?q="))
        self.assertTrue(link["is_search"])
        self.assertIn("Amul", link["url"])

    def test_zepto_uses_verified_search_url(self):
        platform = Platform.objects.create(name="Zepto", slug="zepto", base_url="https://www.zeptonow.com")
        link = build_platform_link(platform, "Maggi Noodles")
        self.assertTrue(link["url"].startswith("https://www.zeptonow.com/search?query="))
        self.assertTrue(link["is_search"])

    def test_unmapped_platform_falls_back_to_base_url_not_search(self):
        platform = Platform.objects.create(name="Swiggy Instamart", slug="swiggy-instamart", base_url="https://www.swiggy.com/instamart")
        link = build_platform_link(platform, "Maggi Noodles")
        self.assertEqual(link["url"], "https://www.swiggy.com/instamart")
        self.assertFalse(link["is_search"])

    def test_query_is_url_encoded(self):
        platform = Platform.objects.create(name="Blinkit", slug="blinkit", base_url="https://blinkit.com")
        link = build_platform_link(platform, "Amul & Sons' Milk")
        self.assertNotIn(" ", link["url"])
        self.assertNotIn("'", link["url"])

    def test_platform_with_no_base_url_and_no_mapping_returns_empty(self):
        platform = Platform.objects.create(name="Unknown Platform", slug="unknown", base_url="")
        link = build_platform_link(platform, "Test Product")
        self.assertEqual(link["url"], "")


class RemoteImageProviderTests(TestCase):
    """Verifies graceful fallback behavior - not real network success,
    which this sandbox cannot exercise (see products/image_providers.py
    docstring). What matters is that a failed lookup/download never
    raises and never leaves a broken image."""

    def setUp(self):
        category = Category.objects.create(name="Test Category Remote")
        subcategory = Subcategory.objects.create(name="Test Sub Remote", category=category)
        self.product = Product.objects.create(
            name="Zzzremotetest Product 1kg", brand="Zzzremotetest",
            subcategory=subcategory, quantity=Decimal("1.000"), unit="kg",
        )

    def tearDown(self):
        from django.conf import settings
        if self.product.image_path:
            (settings.BASE_DIR / "static" / self.product.image_path).unlink(missing_ok=True)

    def test_search_failure_returns_none_not_exception(self):
        from products.image_providers import RemoteImageProvider
        provider = RemoteImageProvider()
        # No mocking needed - this sandbox genuinely has no route to
        # world.openfoodfacts.org, so this exercises the real failure path.
        result = provider.get_image_path(self.product)
        self.assertIsNone(result)

    def test_get_active_providers_falls_back_to_placeholder(self):
        from products.image_providers import get_active_providers
        providers = get_active_providers()
        path = None
        for provider in providers:
            path = provider.get_image_path(self.product)
            if path:
                break
        self.assertIsNotNone(path)  # PlaceholderProvider must always succeed
        self.assertTrue(path.startswith("product_images/generated/"))
