"""Makes the cart item count and the Karnataka location tree available to
every template without every view needing to pass them explicitly."""

from django.core.cache import cache

from .models import District


def cart_count(request):
    cart = request.session.get("cart", {})
    return {"cart_count": sum(cart.values()) if cart else 0}


def location_tree(request):
    """A nested State -> District -> City -> Locality structure, used by
    the location picker's "browse" tab (as an alternative to search) so
    it works entirely off the existing geography models, cascading
    client-side with no extra API round trips - the whole Karnataka tree
    is under ~50 localities, so this is cheap to embed on every page.

    Cached briefly since the geography barely ever changes - avoids
    rebuilding this on every single request across a session.
    """
    tree = cache.get("location_tree_v1")
    if tree is None:
        tree = []
        districts = (
            District.objects.select_related("state")
            .prefetch_related("cities__localities")
            .order_by("name")
        )
        for district in districts:
            cities = []
            for city in district.cities.all():
                localities = [
                    {"id": loc.id, "name": loc.name, "pincode": loc.pincode}
                    for loc in city.localities.all() if loc.is_active
                ]
                if localities:
                    cities.append({"name": city.name, "localities": localities})
            if cities:
                tree.append({"name": district.name, "cities": cities})
        cache.set("location_tree_v1", tree, 60 * 60)  # 1 hour

    return {"location_tree": tree}
