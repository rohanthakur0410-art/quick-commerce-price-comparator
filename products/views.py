"""
Server-rendered frontend views. These call the same service functions as
the API (products/services.py) - one implementation of the comparison/
basket rules, not a separate copy for the frontend.

Location and the comparison basket both live in the session, so neither
requires an account (see README "Why no authentication").
"""

from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from .models import Category, Locality, Platform, PlatformAvailability, PriceHistory, Product
from .services import compare_basket, compare_prices, compute_price_insights

SESSION_LOCALITY_KEY = "locality_id"
SESSION_CART_KEY = "cart"  # {str(product_id): quantity}
DEFAULT_LOCALITY_NAME = "Indiranagar"
PAGE_SIZE = 24


def _get_selected_locality(request):
    locality_id = request.session.get(SESSION_LOCALITY_KEY)
    if locality_id:
        locality = Locality.objects.filter(pk=locality_id, is_active=True).select_related("city").first()
        if locality:
            return locality

    default = Locality.objects.filter(is_active=True, name=DEFAULT_LOCALITY_NAME).select_related("city").first()
    if default:
        return default
    return Locality.objects.filter(is_active=True).select_related("city").first()


def set_locality(request):
    locality_id = request.GET.get("locality_id") or request.POST.get("locality_id")
    if locality_id and Locality.objects.filter(pk=locality_id, is_active=True).exists():
        request.session[SESSION_LOCALITY_KEY] = int(locality_id)
    next_url = request.GET.get("next") or request.POST.get("next") or "home"
    return redirect(next_url)


def _platform_status_for(locality):
    """Every active platform, each marked as servicing this locality or
    not - straight off Platform/PlatformAvailability, never invented.
    Used by the homepage's platform section."""
    if locality is None:
        return []
    available_ids = set(
        PlatformAvailability.objects.filter(locality=locality, status=PlatformAvailability.AVAILABLE)
        .values_list("platform_id", flat=True)
    )
    return [
        {"platform": p, "available": p.id in available_ids}
        for p in Platform.objects.filter(is_active=True).order_by("name")
    ]


def home(request):
    locality = _get_selected_locality(request)
    search_term = request.GET.get("q", "").strip()
    category_filter = request.GET.get("category", "").strip()

    products = Product.objects.filter(is_active=True).select_related("subcategory__category")
    if search_term:
        products = products.filter(
            Q(name__icontains=search_term) | Q(brand__icontains=search_term)
            | Q(subcategory__name__icontains=search_term) | Q(subcategory__category__name__icontains=search_term)
        )
    if category_filter:
        products = products.filter(subcategory__category__name=category_filter)
    products = products.order_by("name")

    paginator = Paginator(products, PAGE_SIZE)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    results = []
    if locality:
        for product in page_obj.object_list:
            comparison = compare_prices(product, locality=locality)
            if comparison.available_count == 0 and not search_term and not category_filter:
                continue
            results.append({"product": product, "comparison": comparison})

    best_deals = sorted(
        (r for r in results if r["comparison"].lowest_price is not None and r["comparison"].savings_vs_next_best),
        key=lambda r: r["comparison"].savings_vs_next_best, reverse=True,
    )[:3] if not search_term and not category_filter else []

    categories = Category.objects.order_by("name")
    popular_terms = ["Milk", "Bread", "Eggs", "Maggi", "Chips", "Shampoo", "Detergent", "Rice"]
    platform_status = _platform_status_for(locality)

    return render(request, "products/home.html", {
        "search_term": search_term, "category_filter": category_filter,
        "results": results, "best_deals": best_deals,
        "locality": locality, "categories": categories, "popular_terms": popular_terms,
        "page_obj": page_obj, "total_count": paginator.count, "platform_status": platform_status,
    })


def product_detail(request, pk):
    product = get_object_or_404(Product, pk=pk, is_active=True)
    locality = _get_selected_locality(request)

    comparison = compare_prices(product, locality=locality) if locality else None
    insights = compute_price_insights(product, locality=locality) if locality else None

    history = []
    chart_points = []
    if locality:
        history = list(
            PriceHistory.objects.filter(product_offer__product=product, product_offer__locality=locality)
            .select_related("product_offer__platform").order_by("-recorded_at")[:60]
        )
        chart_points = [
            {"date": h.recorded_at.strftime("%b %d %H:%M"), "price": float(h.price), "platform": h.product_offer.platform.name}
            for h in reversed(history)
        ]

    return render(request, "products/product_detail.html", {
        "product": product, "comparison": comparison, "insights": insights,
        "history": history, "chart_points": chart_points, "locality": locality,
    })


# ---------------- Basket / cart ----------------

def _get_cart(request):
    return request.session.get(SESSION_CART_KEY, {})


def _save_cart(request, cart):
    request.session[SESSION_CART_KEY] = cart
    request.session.modified = True


def cart_add(request, pk):
    get_object_or_404(Product, pk=pk, is_active=True)
    cart = _get_cart(request)
    cart[str(pk)] = cart.get(str(pk), 0) + 1
    _save_cart(request, cart)
    return redirect(request.META.get("HTTP_REFERER", "home"))


def cart_remove(request, pk):
    cart = _get_cart(request)
    cart.pop(str(pk), None)
    _save_cart(request, cart)
    return redirect("cart")


def cart_update(request, pk):
    try:
        qty = max(1, min(50, int(request.POST.get("quantity", 1))))
    except (TypeError, ValueError):
        qty = 1
    cart = _get_cart(request)
    if str(pk) in cart:
        cart[str(pk)] = qty
        _save_cart(request, cart)
    return redirect("cart")


def cart_view(request):
    locality = _get_selected_locality(request)
    cart = _get_cart(request)
    product_ids = [int(pid) for pid in cart.keys()]
    products_by_id = {p.id: p for p in Product.objects.filter(id__in=product_ids, is_active=True)}

    # Drop any cart entries whose product no longer exists.
    items = [(products_by_id[pid], qty) for pid, qty in ((int(k), v) for k, v in cart.items()) if pid in products_by_id]

    result = None
    if items and locality:
        result = compare_basket(items, locality)

    return render(request, "products/cart.html", {
        "locality": locality, "items": items, "result": result, "cart_count": sum(cart.values()),
    })
