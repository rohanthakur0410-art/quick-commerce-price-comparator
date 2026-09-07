from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("products.api_urls")),
    path("", include("products.urls")),
]
