"""
Generates a category/brand-aware placeholder image per product.

Real product photography can't be fetched automatically here (no
reliable, legally-clear source for 2,500+ SKUs), so instead of random or
generic "no image" boxes, every product gets a small SVG card: a
category-tinted background, a solid-color monogram badge with the
brand's initials, and the category name - deterministic per product
(same product always renders the same way), fast (a few hundred bytes,
no image processing), and never misrepresented as a real photo.

Generated once to disk under static/product_images/generated/<sku>.svg
and the path cached on Product.image_path - see
management/commands/generate_product_images.py - so it is never
regenerated on a page request.
"""

import os
from xml.sax.saxutils import escape

from django.conf import settings

# (background tint, accent color) per top-level category. Deliberately
# soft/muted, not a rainbow - matches the rest of the UI's restrained
# palette.
CATEGORY_COLORS = {
    "Grocery & Staples": ("#fdf3e7", "#b06a1a"),
    "Dairy & Breakfast": ("#eaf3fc", "#1d6fb8"),
    "Snacks & Packaged Food": ("#fdefe6", "#c9531e"),
    "Beverages": ("#e8f6f1", "#0f8a6c"),
    "Fruits & Vegetables": ("#edf9e7", "#3f9142"),
    "Frozen Food": ("#eaf1fc", "#3457a6"),
    "Personal Care": ("#fbecf3", "#b83b78"),
    "Baby Care": ("#f1eefb", "#6a45c9"),
    "Household": ("#eceff2", "#48586b"),
    "Pet Care": ("#faf1e2", "#a97327"),
    "Home & Kitchen": ("#f4eee4", "#8a5a2b"),
    "Stationery": ("#eaf5f9", "#1c7fa0"),
    "Electronics & Accessories": ("#eaecf5", "#3c4a8c"),
}
_DEFAULT_COLORS = ("#f1f2f4", "#5b6272")

IMAGE_DIR = "product_images/generated"


def _initials(brand: str) -> str:
    words = [w for w in brand.strip().split() if w]
    letters = "".join(w[0] for w in words[:2]).upper()
    return letters or "?"


def generate_placeholder_svg(product) -> str:
    category_name = product.category.name
    bg, accent = CATEGORY_COLORS.get(category_name, _DEFAULT_COLORS)
    initials = escape(_initials(product.brand))
    category_label = escape(category_name)
    size_label = escape(f"{float(product.quantity):g}{product.unit}")

    return f'''<svg viewBox="0 0 300 300" xmlns="http://www.w3.org/2000/svg">
  <rect width="300" height="300" rx="16" fill="{bg}"/>
  <circle cx="150" cy="122" r="54" fill="{accent}"/>
  <text x="150" y="140" font-family="Arial, sans-serif" font-size="42" font-weight="700"
        fill="#ffffff" text-anchor="middle">{initials}</text>
  <text x="150" y="228" font-family="Arial, sans-serif" font-size="15" font-weight="600"
        fill="#2a2d33" text-anchor="middle">{category_label}</text>
  <rect x="110" y="244" width="80" height="22" rx="11" fill="#ffffff" opacity="0.85"/>
  <text x="150" y="259" font-family="Arial, sans-serif" font-size="12" font-weight="600"
        fill="{accent}" text-anchor="middle">{size_label}</text>
</svg>'''


def image_relative_path_for(product) -> str:
    return f"{IMAGE_DIR}/{product.sku}.svg"


def ensure_product_image(product) -> bool:
    """Writes the SVG to disk if it doesn't already exist, and sets
    product.image_path (saving only if it changed). Returns True if the
    file was (re)generated."""
    relative_path = image_relative_path_for(product)
    static_dir = settings.BASE_DIR / "static" / IMAGE_DIR
    os.makedirs(static_dir, exist_ok=True)
    file_path = static_dir / f"{product.sku}.svg"

    generated = False
    if not file_path.exists():
        file_path.write_text(generate_placeholder_svg(product), encoding="utf-8")
        generated = True

    if product.image_path != relative_path:
        product.image_path = relative_path
        product.save(update_fields=["image_path"])

    return generated
