from decimal import Decimal

from django.db import models

from .normalization import generate_sku, normalize_product_name


# ============================================================
# Geography: State -> District -> City -> Locality (-> pincode)
#
# Karnataka is the first-populated state, but nothing here is
# Karnataka-specific - adding another state is new rows, not new code
# (see README "How to add another state").
# ============================================================

class State(models.Model):
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=4, blank=True, help_text="e.g. 'KA'")

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class District(models.Model):
    name = models.CharField(max_length=100)
    state = models.ForeignKey(State, on_delete=models.CASCADE, related_name="districts")

    class Meta:
        ordering = ["name"]
        constraints = [models.UniqueConstraint(fields=["state", "name"], name="uniq_district_per_state")]

    def __str__(self):
        return f"{self.name}, {self.state.code or self.state.name}"


class City(models.Model):
    name = models.CharField(max_length=100)
    district = models.ForeignKey(District, on_delete=models.CASCADE, related_name="cities")

    class Meta:
        ordering = ["name"]
        constraints = [models.UniqueConstraint(fields=["district", "name"], name="uniq_city_per_district")]
        indexes = [models.Index(fields=["name"], name="idx_city_name")]

    def __str__(self):
        return self.name


class Locality(models.Model):
    """The finest-grained service area - what a ProductOffer and
    PlatformAvailability are actually scoped to."""

    name = models.CharField(max_length=100)
    city = models.ForeignKey(City, on_delete=models.CASCADE, related_name="localities")
    pincode = models.CharField(max_length=6, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["city__name", "name"]
        verbose_name_plural = "Localities"
        constraints = [models.UniqueConstraint(fields=["city", "name"], name="uniq_locality_per_city")]
        indexes = [
            models.Index(fields=["city", "name"], name="idx_locality_city_name"),
            models.Index(fields=["pincode"], name="idx_locality_pincode"),
        ]

    def __str__(self):
        return f"{self.name}, {self.city.name}"

    @property
    def state(self):
        return self.city.district.state


# ============================================================
# Platforms & their availability by location
# ============================================================

class Platform(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    base_url = models.URLField(blank=True)
    primary_color = models.CharField(max_length=7, blank=True)
    is_active = models.BooleanField(default=True)

    # Simulated fee data (see README "Demo vs Live data") - used by the
    # basket optimizer. Never presented as real fees; always labelled
    # "simulated" in the UI/API when displayed.
    base_delivery_fee = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal("0.00"))
    free_delivery_above = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class PlatformAvailability(models.Model):
    """Whether a platform services a given locality at all - independent
    of any single product's price. Fail-closed by design: if no row
    exists for (platform, locality), the platform is treated as
    unavailable there (see services.py) rather than assumed available.
    """

    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    UNKNOWN = "unknown"
    STATUS_CHOICES = [(AVAILABLE, "Available"), (UNAVAILABLE, "Unavailable"), (UNKNOWN, "Unknown")]

    platform = models.ForeignKey(Platform, on_delete=models.CASCADE, related_name="availability")
    locality = models.ForeignKey(Locality, on_delete=models.CASCADE, related_name="platform_availability")
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=UNKNOWN)

    class Meta:
        verbose_name_plural = "Platform availability"
        constraints = [models.UniqueConstraint(fields=["platform", "locality"], name="uniq_platform_locality")]
        indexes = [models.Index(fields=["locality", "status"], name="idx_avail_locality_status")]

    def __str__(self):
        return f"{self.platform.name} @ {self.locality} - {self.status}"


# ============================================================
# Catalog: Category/Subcategory taxonomy + canonical Product
# ============================================================

class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "Categories"

    def __str__(self):
        return self.name


class Subcategory(models.Model):
    name = models.CharField(max_length=100)
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name="subcategories")

    class Meta:
        ordering = ["category__name", "name"]
        verbose_name_plural = "Subcategories"
        constraints = [models.UniqueConstraint(fields=["category", "name"], name="uniq_subcategory_per_category")]

    def __str__(self):
        return f"{self.name} ({self.category.name})"


UNIT_CHOICES = [("kg", "kg"), ("g", "g"), ("l", "L"), ("ml", "ml"), ("pcs", "pcs"), ("pack", "pack")]


class Product(models.Model):
    """A canonical product - independent of platform or location.

    Two records are the *same* canonical product only if brand,
    normalized_name, quantity, AND unit all match (see
    products/normalization.py) - quantity/unit are never fuzzy-matched,
    so "Milk 500ml" and "Milk 1L" are always distinct products even
    though their names are otherwise identical.
    """

    name = models.CharField(max_length=255)
    brand = models.CharField(max_length=120)
    subcategory = models.ForeignKey(Subcategory, on_delete=models.PROTECT, related_name="products")
    quantity = models.DecimalField(max_digits=10, decimal_places=3)
    unit = models.CharField(max_length=10, choices=UNIT_CHOICES)
    normalized_name = models.CharField(max_length=255, editable=False)
    sku = models.CharField(max_length=64, unique=True, blank=True)
    image_path = models.CharField(
        max_length=255, blank=True,
        help_text="Relative static path to a generated placeholder image (see products/imaging.py). "
                   "Stored once so it's never regenerated on every page request.",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["brand", "normalized_name", "quantity", "unit"], name="uniq_canonical_product"
            ),
        ]
        indexes = [
            models.Index(fields=["name"], name="idx_product_name"),
            models.Index(fields=["brand"], name="idx_product_brand"),
            models.Index(fields=["normalized_name"], name="idx_product_normalized_name"),
            models.Index(fields=["subcategory"], name="idx_product_subcategory"),
        ]

    def save(self, *args, **kwargs):
        self.normalized_name = normalize_product_name(self.name)
        if not self.sku:
            self.sku = generate_sku(self.brand, self.name, self.quantity, self.unit)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.quantity}{self.unit})"

    @property
    def category(self):
        return self.subcategory.category


# ============================================================
# Pricing: ProductOffer (latest known state) + PriceHistory (immutable
# log of every observed change)
# ============================================================

class ProductOffer(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="offers")
    platform = models.ForeignKey(Platform, on_delete=models.CASCADE, related_name="offers")
    locality = models.ForeignKey(Locality, on_delete=models.CASCADE, related_name="offers")

    external_product_id = models.CharField(max_length=120, blank=True)
    source_url = models.URLField(blank=True)
    current_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    is_available = models.BooleanField(default=True)
    delivery_minutes = models.PositiveSmallIntegerField(null=True, blank=True)
    promotion_text = models.CharField(max_length=120, blank=True)

    #: Always True in this project - see README "Demo vs Live data".
    #: Kept as a real field (not just documentation) so the data model
    #: itself can represent a future live source without a schema change.
    is_demo = models.BooleanField(default=True)
    last_checked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["current_price"]
        constraints = [
            models.UniqueConstraint(fields=["product", "platform", "locality"], name="uniq_offer_product_platform_locality"),
        ]
        indexes = [
            models.Index(fields=["product", "locality"], name="idx_offer_product_locality"),
            models.Index(fields=["platform", "locality"], name="idx_offer_platform_locality"),
            models.Index(fields=["is_available", "current_price"], name="idx_offer_available_price"),
        ]

    def __str__(self):
        return f"{self.product.name} @ {self.platform.name} ({self.locality})"


class PriceHistory(models.Model):
    product_offer = models.ForeignKey(ProductOffer, on_delete=models.CASCADE, related_name="price_history")
    price = models.DecimalField(max_digits=10, decimal_places=2)
    is_available = models.BooleanField(default=True)
    promotion_text = models.CharField(max_length=120, blank=True)
    recorded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-recorded_at"]
        verbose_name_plural = "Price histories"
        indexes = [models.Index(fields=["product_offer", "-recorded_at"], name="idx_history_offer_time")]

    def __str__(self):
        return f"{self.product_offer} - Rs.{self.price} @ {self.recorded_at:%Y-%m-%d %H:%M}"
