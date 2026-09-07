from django.urls import path

from . import api_views

urlpatterns = [
    path("products/", api_views.ProductListView.as_view(), name="api-product-list"),
    path("products/<int:pk>/", api_views.ProductDetailView.as_view(), name="api-product-detail"),
    path("products/<int:pk>/compare/", api_views.ProductCompareView.as_view(), name="api-product-compare"),
    path("products/<int:pk>/history/", api_views.ProductHistoryView.as_view(), name="api-product-history"),
    path("platforms/", api_views.PlatformListView.as_view(), name="api-platform-list"),
    path("localities/", api_views.LocalityListView.as_view(), name="api-locality-list"),
    path("basket/compare/", api_views.BasketCompareView.as_view(), name="api-basket-compare"),
]
