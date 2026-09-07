from django.contrib import admin

from .models import (
    Category, City, District, Locality, PlatformAvailability, PriceHistory,
    Platform, Product, ProductOffer, State, Subcategory,
)


@admin.register(State)
class StateAdmin(admin.ModelAdmin):
    list_display = ["name", "code"]
    search_fields = ["name", "code"]


@admin.register(District)
class DistrictAdmin(admin.ModelAdmin):
    list_display = ["name", "state"]
    list_filter = ["state"]
    search_fields = ["name"]
    autocomplete_fields = ["state"]


@admin.register(City)
class CityAdmin(admin.ModelAdmin):
    list_display = ["name", "district"]
    list_filter = ["district__state"]
    search_fields = ["name"]
    autocomplete_fields = ["district"]


@admin.register(Locality)
class LocalityAdmin(admin.ModelAdmin):
    list_display = ["name", "city", "pincode", "is_active"]
    list_filter = ["city__district__state", "is_active"]
    search_fields = ["name", "city__name", "pincode"]
    autocomplete_fields = ["city"]


@admin.register(Platform)
class PlatformAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "is_active", "base_delivery_fee", "free_delivery_above"]
    list_filter = ["is_active"]
    search_fields = ["name", "slug"]
    prepopulated_fields = {"slug": ("name",)}


@admin.register(PlatformAvailability)
class PlatformAvailabilityAdmin(admin.ModelAdmin):
    list_display = ["platform", "locality", "status"]
    list_filter = ["platform", "status", "locality__city"]
    search_fields = ["locality__name", "locality__city__name"]
    autocomplete_fields = ["platform", "locality"]


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ["name"]
    search_fields = ["name"]


@admin.register(Subcategory)
class SubcategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "category"]
    list_filter = ["category"]
    search_fields = ["name"]
    autocomplete_fields = ["category"]


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ["name", "brand", "subcategory", "quantity", "unit", "is_active", "updated_at"]
    list_filter = ["subcategory__category", "is_active"]
    search_fields = ["name", "brand", "sku"]
    autocomplete_fields = ["subcategory"]
    ordering = ["name"]


@admin.register(ProductOffer)
class ProductOfferAdmin(admin.ModelAdmin):
    list_display = ["product", "platform", "locality", "current_price", "is_available", "delivery_minutes", "is_demo", "last_checked_at"]
    list_filter = ["platform", "is_available", "locality__city"]
    search_fields = ["product__name", "platform__name", "locality__name"]
    autocomplete_fields = ["product", "platform", "locality"]


@admin.register(PriceHistory)
class PriceHistoryAdmin(admin.ModelAdmin):
    list_display = ["product_offer", "price", "is_available", "recorded_at"]
    list_filter = ["is_available", "recorded_at"]
    search_fields = ["product_offer__product__name", "product_offer__platform__name", "product_offer__locality__name"]
    ordering = ["-recorded_at"]
    date_hierarchy = "recorded_at"
