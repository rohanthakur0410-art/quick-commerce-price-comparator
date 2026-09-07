"""
Product-name normalization used for matching/deduplication during
ingestion (see management/commands/import_products.py).

Design goal (per README "Product Normalization & Matching"): be
conservative. It's fine to under-match (two records that are really the
same product end up as two Product rows) - that's an easy manual fix. A
false *positive* match (two different products merged into one) silently
corrupts price comparisons, which is worse. So this only strips
formatting noise (case, punctuation, embedded size tokens) - it never
does fuzzy/similarity matching, and the dedup key always includes
quantity+unit as hard, non-fuzzy fields.
"""

import re
import unicodedata

# Size/unit tokens that commonly appear embedded in a raw product name
# (e.g. "Amul Taaza Milk 1L", "Maggi Noodles - 70 g") and should be
# stripped for normalized_name, since quantity/unit are tracked as their
# own structured fields - keeping them in the text key would make
# "Milk 1L" and "Milk 1 L" normalize differently for no good reason.
_SIZE_TOKEN_RE = re.compile(
    r"[\-–—]?\s*\d+(\.\d+)?\s*(kg|g|gm|gms|ml|l|ltr|litre|litres|pcs|pc|pack|packs)\b",
    re.IGNORECASE,
)
_PUNCT_RE = re.compile(r"[^a-z0-9\s]")
_MULTI_SPACE_RE = re.compile(r"\s+")

# unit -> canonical short form, and the size-string parser below.
UNIT_CHOICES = ["kg", "g", "l", "ml", "pcs", "pack"]
_UNIT_ALIASES = {
    "kg": "kg", "kgs": "kg",
    "g": "g", "gm": "g", "gms": "g", "grams": "g",
    "l": "l", "ltr": "l", "litre": "l", "litres": "l",
    "ml": "ml",
    "pcs": "pcs", "pc": "pcs", "piece": "pcs", "pieces": "pcs",
    "pack": "pack", "packs": "pack",
}
_SIZE_PARSE_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(kg|g|gm|gms|ml|l|ltr|litre|litres|pcs|pc|pack|packs)", re.IGNORECASE)


def normalize_product_name(raw_name: str) -> str:
    """Lowercase, strip punctuation and embedded size tokens, collapse
    whitespace. Deterministic and side-effect-free."""
    text = unicodedata.normalize("NFKD", raw_name or "").lower()
    text = _SIZE_TOKEN_RE.sub(" ", text)
    text = _PUNCT_RE.sub(" ", text)
    text = _MULTI_SPACE_RE.sub(" ", text).strip()
    return text


def parse_size(size_text: str):
    """Parse a size string like '1kg', '500 ml', '6 pcs' into
    (quantity: Decimal-friendly str, unit: str) using the canonical unit
    set. Returns (None, None) if it can't be parsed - callers treat that
    as an invalid record rather than guessing."""
    if not size_text:
        return None, None
    match = _SIZE_PARSE_RE.search(size_text.strip().lower())
    if not match:
        return None, None
    quantity, raw_unit = match.groups()
    unit = _UNIT_ALIASES.get(raw_unit.lower())
    if unit is None:
        return None, None
    return quantity, unit


def dedup_key(brand: str, normalized_name: str, quantity, unit: str) -> tuple:
    """The matching key used to decide whether two records describe the
    same canonical product. Brand and quantity/unit are exact-match
    (never fuzzy) - only the name goes through normalize_product_name.
    """
    return (brand.strip().lower(), normalized_name, str(quantity), unit)


def generate_sku(brand: str, name: str, quantity, unit: str) -> str:
    """A short, readable, mostly-unique identifier derived from the
    product's own fields - not a real platform SKU (we have none), just
    a stable external_product_id-style handle."""
    raw = f"{brand}-{name}-{quantity}{unit}".lower()
    slug = re.sub(r"[^a-z0-9]+", "-", raw).strip("-")
    return slug[:60]
