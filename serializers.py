from rest_framework import serializers

from .models import Category, Locality, PriceHistory, Platform, Product, Subcategory


class PlatformSerializer(serializers.ModelSerializer):
    class Meta:
        model = Platform
        fields = ["id", "name", "slug", "base_url", "primary_color", "is_active",
                  "base_delivery_fee", "free_delivery_above"]


class LocalitySerializer(serializers.ModelSerializer):
    city = serializers.CharField(source="city.name")
    district = serializers.CharField(source="city.district.name")
    state = serializers.CharField(source="city.district.state.name")

    class Meta:
        model = Locality
        fields = ["id", "name", "city", "district", "state", "pincode"]


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name"]


class SubcategorySerializer(serializers.ModelSerializer):
    category = serializers.CharField(source="category.name")

    class Meta:
        model = Subcategory
        fields = ["id", "name", "category"]


class ProductListSerializer(serializers.ModelSerializer):
    """Lightweight representation for GET /api/products/?search=...&locality=<id>.

    lowest_price/best_platform are populated by the view (from the
    comparison service) only when a locality is given, since price is
    never a property of a product alone.
    """

    category = serializers.CharField(source="subcategory.category.name", read_only=True)
    subcategory = serializers.CharField(source="subcategory.name", read_only=True)
    lowest_price = serializers.SerializerMethodField()
    best_platform = serializers.SerializerMethodField()
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = ["id", "name", "brand", "category", "subcategory", "quantity", "unit",
                  "lowest_price", "best_platform", "image_url"]

    def get_lowest_price(self, product):
        return self.context.get("comparisons", {}).get(product.id, {}).get("lowest_price")

    def get_best_platform(self, product):
        return self.context.get("comparisons", {}).get(product.id, {}).get("best_platform")

    def get_image_url(self, product):
        return f"/static/{product.image_path}" if product.image_path else None


class ProductDetailSerializer(serializers.ModelSerializer):
    category = serializers.CharField(source="subcategory.category.name", read_only=True)
    subcategory = serializers.CharField(source="subcategory.name", read_only=True)
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = ["id", "name", "brand", "category", "subcategory", "quantity", "unit", "sku",
                  "image_url", "created_at", "updated_at"]

    def get_image_url(self, product):
        return f"/static/{product.image_path}" if product.image_path else None


class OfferRowSerializer(serializers.Serializer):
    platform = serializers.CharField(source="platform_name")
    platform_slug = serializers.CharField()
    price = serializers.DecimalField(max_digits=10, decimal_places=2, allow_null=True)
    available = serializers.BooleanField(source="is_available")
    serviceable = serializers.BooleanField()
    delivery_minutes = serializers.IntegerField(allow_null=True)
    promotion = serializers.CharField(source="promotion_text", allow_blank=True)
    last_checked_at = serializers.CharField(allow_null=True)
    is_demo = serializers.SerializerMethodField()
    buy_link = serializers.SerializerMethodField()

    def get_is_demo(self, obj):
        return True  # every offer in this project is simulated - see README

    def get_buy_link(self, obj):
        return {"url": obj.buy_url, "is_search": obj.buy_url_is_search}


class ComparisonResultSerializer(serializers.Serializer):
    product = serializers.CharField(source="product.name")
    locality = serializers.SerializerMethodField()
    offers = OfferRowSerializer(source="rows", many=True)
    best_price = serializers.SerializerMethodField()
    savings_vs_next_best = serializers.DecimalField(max_digits=10, decimal_places=2, allow_null=True)
    available_count = serializers.IntegerField()
    total_count = serializers.IntegerField()

    def get_locality(self, obj):
        return str(obj.locality) if obj.locality else None

    def get_best_price(self, obj):
        if obj.best_platform is None:
            return None
        return {"platform": obj.best_platform, "price": obj.lowest_price}


class PriceInsightsSerializer(serializers.Serializer):
    current_price = serializers.DecimalField(max_digits=10, decimal_places=2, allow_null=True)
    previous_price = serializers.DecimalField(max_digits=10, decimal_places=2, allow_null=True)
    change_amount = serializers.DecimalField(max_digits=10, decimal_places=2, allow_null=True)
    change_percent = serializers.FloatField(allow_null=True)
    lowest_recorded = serializers.DecimalField(max_digits=10, decimal_places=2, allow_null=True)
    highest_recorded = serializers.DecimalField(max_digits=10, decimal_places=2, allow_null=True)
    average_recent = serializers.DecimalField(max_digits=10, decimal_places=2, allow_null=True)
    sample_size = serializers.IntegerField()


class PriceHistorySerializer(serializers.ModelSerializer):
    platform = serializers.CharField(source="product_offer.platform.name", read_only=True)
    locality = serializers.CharField(source="product_offer.locality", read_only=True)

    class Meta:
        model = PriceHistory
        fields = ["id", "platform", "locality", "price", "is_available", "promotion_text", "recorded_at"]


# ---------------- Basket ----------------

class BasketItemInputSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=1, max_value=50)


class BasketItemOfferSerializer(serializers.Serializer):
    product = serializers.CharField(source="product.name")
    quantity = serializers.IntegerField()
    best_platform = serializers.CharField(allow_null=True)
    best_price = serializers.DecimalField(max_digits=10, decimal_places=2, allow_null=True)
    prices_by_platform = serializers.DictField(child=serializers.DecimalField(max_digits=10, decimal_places=2))


class PlatformTotalSerializer(serializers.Serializer):
    platform = serializers.CharField(source="platform_name")
    can_fulfill_all = serializers.BooleanField()
    subtotal = serializers.DecimalField(max_digits=10, decimal_places=2, allow_null=True)
    delivery_fee = serializers.DecimalField(max_digits=10, decimal_places=2, allow_null=True)
    total = serializers.DecimalField(max_digits=10, decimal_places=2, allow_null=True)
    fee_is_simulated = serializers.BooleanField()


class SplitGroupSerializer(serializers.Serializer):
    platform = serializers.CharField(source="platform_name")
    items = serializers.SerializerMethodField()
    subtotal = serializers.DecimalField(max_digits=10, decimal_places=2)
    delivery_fee = serializers.DecimalField(max_digits=10, decimal_places=2)
    total = serializers.DecimalField(max_digits=10, decimal_places=2)

    def get_items(self, obj):
        return [
            {"product": name, "quantity": qty, "unit_price": str(price), "line_total": str(total)}
            for name, qty, price, total in obj.items
        ]


class BasketResultSerializer(serializers.Serializer):
    locality = serializers.SerializerMethodField()
    items = BasketItemOfferSerializer(many=True)
    single_platform_totals = PlatformTotalSerializer(many=True)
    best_single_platform = PlatformTotalSerializer(allow_null=True)
    optimized_split = SplitGroupSerializer(many=True)
    optimized_total = serializers.DecimalField(max_digits=10, decimal_places=2, allow_null=True)
    recommend_split = serializers.BooleanField()
    savings_vs_single = serializers.DecimalField(max_digits=10, decimal_places=2, allow_null=True)
    explanation = serializers.ListField(child=serializers.CharField())

    def get_locality(self, obj):
        return str(obj.locality)
