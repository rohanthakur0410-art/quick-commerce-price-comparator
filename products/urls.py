from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("locality/set/", views.set_locality, name="set-locality"),
    path("products/<int:pk>/", views.product_detail, name="product-detail"),
    path("cart/", views.cart_view, name="cart"),
    path("cart/add/<int:pk>/", views.cart_add, name="cart-add"),
    path("cart/remove/<int:pk>/", views.cart_remove, name="cart-remove"),
    path("cart/update/<int:pk>/", views.cart_update, name="cart-update"),
]
