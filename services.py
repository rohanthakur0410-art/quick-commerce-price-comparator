"""
Comparison, price-insight, and basket-optimization logic.

Kept out of views.py deliberately: the API and the frontend both call
these functions, so there's exactly one implementation of "what's the
best deal" and "how should this basket be split", not two.
"""

import logging
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional

from .models import PriceHistory, Platform, Product, ProductOffer
from .platform_links import build_platform_link
from .pricing import available_platforms_for, ensure_offers

logger = logging.getLogger("products")

#: A cross-platform split is only recommended if it beats the best
#: single-platform total by at least this much - a few rupees of
#: "savings" isn't worth juggling two orders in real life.
MIN_SPLIT_SAVINGS = Decimal("15.00")


# ============================================================
# Single-product comparison
# ============================================================

@dataclass
class OfferRow:
    platform_name: str
    platform_slug: str
    price: Optional[Decimal]
    is_available: bool
    #: Whether this platform services the locality at all (per
    #: PlatformAvailability). False means "not available in this area" -
    #: distinct from is_available=False, which means "serviced here, but
    #: this particular item is out of stock." Never conflate the two in
    #: the UI - one is a coverage fact, the other is a stock fact.
    serviceable: bool
    delivery_minutes: Optional[int]
    promotion_text: str
    last_checked_at: Optional[str]
    offer_id: Optional[int]
    buy_url: str
    buy_url_is_search: bool


@dataclass
class ComparisonResult:
    product: Product
    locality: Optional["products.models.Locality"]
    rows: list
    lowest_price: Optional[Decimal]
    highest_price: Optional[Decimal]
    best_platform: Optional[str]
    savings_vs_next_best: Optional[Decimal]
    available_count: int
    total_count: int


def compare_prices(product: Product, locality=None) -> ComparisonResult:
    """Build a price comparison for one product in one locality.

    Every active platform is represented in the result - not just the
    ones currently servicing this locality. A platform with no
    'available' PlatformAvailability row for this locality gets a row
    with serviceable=False and price=None (never a fabricated price);
    it's still shown, just clearly marked "not available in this area."
    Offers for serviceable platforms are materialized on demand.
    """
    if locality is None:
        return ComparisonResult(product, None, [], None, None, None, None, 0, 0)

    ensure_offers(product, locality)

    available_platform_ids = set(available_platforms_for(locality).values_list("id", flat=True))
    offers_by_platform = {
        o.platform_id: o
        for o in ProductOffer.objects.filter(
            product=product, locality=locality, platform_id__in=available_platform_ids
        ).select_related("platform")
    }

    rows = []
    for platform in Platform.objects.filter(is_active=True).order_by("name"):
        link = build_platform_link(platform, product.name)

        if platform.id not in available_platform_ids:
            rows.append(OfferRow(
                platform_name=platform.name, platform_slug=platform.slug, price=None,
                is_available=False, serviceable=False, delivery_minutes=None,
                promotion_text="", last_checked_at=None, offer_id=None,
                buy_url=link["url"], buy_url_is_search=link["is_search"],
            ))
            continue

        offer = offers_by_platform.get(platform.id)
        if offer is None:
            # Serviceable here, but pricing it failed (simulated provider
            # error) - still shown, just with no current price.
            rows.append(OfferRow(
                platform_name=platform.name, platform_slug=platform.slug, price=None,
                is_available=False, serviceable=True, delivery_minutes=None,
                promotion_text="", last_checked_at=None, offer_id=None,
                buy_url=link["url"], buy_url_is_search=link["is_search"],
            ))
            continue

        rows.append(OfferRow(
            platform_name=platform.name, platform_slug=platform.slug, price=offer.current_price,
            is_available=offer.is_available, serviceable=True, delivery_minutes=offer.delivery_minutes,
            promotion_text=offer.promotion_text,
            last_checked_at=offer.last_checked_at.isoformat() if offer.last_checked_at else None,
            offer_id=offer.id, buy_url=link["url"], buy_url_is_search=link["is_search"],
        ))

    available_rows = sorted((r for r in rows if r.is_available and r.price is not None), key=lambda r: r.price)
    unavailable_rows = [r for r in rows if not (r.is_available and r.price is not None)]
    # Show "out of stock but serviceable" before "not available in this
    # area" - the latter is less actionable/relevant to the user.
    unavailable_rows.sort(key=lambda r: not r.serviceable)

    lowest_price = available_rows[0].price if available_rows else None
    highest_price = available_rows[-1].price if available_rows else None
    best_platform = available_rows[0].platform_name if available_rows else None
    savings = (
        (available_rows[1].price - available_rows[0].price)
        if len(available_rows) > 1 else None
    )

    return ComparisonResult(
        product=product,
        locality=locality,
        rows=available_rows + unavailable_rows,
        lowest_price=lowest_price,
        highest_price=highest_price,
        best_platform=best_platform,
        savings_vs_next_best=savings,
        available_count=len(available_rows),
        total_count=len(rows),
    )


# ============================================================
# Price insights (change/trend, from history)
# ============================================================

@dataclass
class PriceInsights:
    current_price: Optional[Decimal]
    previous_price: Optional[Decimal]
    change_amount: Optional[Decimal]
    change_percent: Optional[float]
    lowest_recorded: Optional[Decimal]
    highest_recorded: Optional[Decimal]
    average_recent: Optional[Decimal]
    sample_size: int


def compute_price_insights(product: Product, locality=None, recent_n: int = 7) -> PriceInsights:
    """Change/trend insights computed from stored PriceHistory - nothing
    here is invented; if there's no history yet, every field is None."""
    history_qs = PriceHistory.objects.filter(product_offer__product=product)
    if locality is not None:
        history_qs = history_qs.filter(product_offer__locality=locality)
    history_qs = history_qs.select_related("product_offer").order_by("-recorded_at")

    recent_entries = list(history_qs[: recent_n * 5])
    if not recent_entries:
        return PriceInsights(None, None, None, None, None, None, None, 0)

    current_price = recent_entries[0].price
    previous_price = recent_entries[1].price if len(recent_entries) > 1 else None
    change_amount = (current_price - previous_price) if previous_price is not None else None
    change_percent = (
        float(change_amount / previous_price * 100) if change_amount is not None and previous_price else None
    )

    prices = [e.price for e in recent_entries if e.is_available]
    lowest_recorded = min(prices) if prices else None
    highest_recorded = max(prices) if prices else None
    average_recent = (sum(prices) / len(prices)) if prices else None

    return PriceInsights(
        current_price=current_price, previous_price=previous_price,
        change_amount=change_amount, change_percent=change_percent,
        lowest_recorded=lowest_recorded, highest_recorded=highest_recorded,
        average_recent=average_recent, sample_size=len(recent_entries),
    )


# ============================================================
# Basket comparison + cross-platform optimization
# ============================================================

@dataclass
class BasketItemOffer:
    product: Product
    quantity: int
    prices_by_platform: dict  # platform_name -> Decimal (available offers only)
    best_platform: Optional[str]
    best_price: Optional[Decimal]


@dataclass
class PlatformTotal:
    platform_name: str
    can_fulfill_all: bool
    subtotal: Optional[Decimal]
    delivery_fee: Optional[Decimal]
    total: Optional[Decimal]
    fee_is_simulated: bool = True


@dataclass
class SplitGroup:
    platform_name: str
    items: list  # list of (product_name, quantity, unit_price, line_total)
    subtotal: Decimal
    delivery_fee: Decimal
    total: Decimal


@dataclass
class BasketResult:
    items: list  # BasketItemOffer
    locality: "products.models.Locality"
    single_platform_totals: list  # PlatformTotal, sorted by total
    best_single_platform: Optional[PlatformTotal]
    optimized_split: list  # SplitGroup
    optimized_total: Optional[Decimal]
    recommend_split: bool
    savings_vs_single: Optional[Decimal]
    explanation: list  # list of str, human-readable


def _platform_fee(platform, subtotal: Decimal) -> Decimal:
    """Simulated delivery fee for one platform's sub-order. Always
    labelled as simulated wherever it's surfaced (API/UI) - see
    Platform.base_delivery_fee / free_delivery_above in models.py."""
    if platform.free_delivery_above is not None and subtotal >= platform.free_delivery_above:
        return Decimal("0.00")
    return platform.base_delivery_fee


def compare_basket(items: list, locality) -> BasketResult:
    """items: list of (Product, quantity). Compares buying the whole
    basket from a single platform vs. splitting it across platforms."""
    from .models import Platform

    platform_objs = {p.id: p for p in available_platforms_for(locality)}

    basket_items = []
    # platform_id -> list of (product, qty, unit_price)
    per_platform_lines = {pid: [] for pid in platform_objs}

    for product, qty in items:
        comparison = compare_prices(product, locality)
        prices_by_platform = {row.platform_name: row.price for row in comparison.rows if row.is_available and row.price is not None}
        basket_items.append(BasketItemOffer(
            product=product, quantity=qty, prices_by_platform=prices_by_platform,
            best_platform=comparison.best_platform, best_price=comparison.lowest_price,
        ))
        for row in comparison.rows:
            if row.is_available and row.price is not None:
                platform_id = next((pid for pid, p in platform_objs.items() if p.name == row.platform_name), None)
                if platform_id is not None:
                    per_platform_lines[platform_id].append((product, qty, row.price))

    # --- Single-platform totals: only platforms that can supply every item ---
    single_totals = []
    for platform_id, platform in platform_objs.items():
        lines = per_platform_lines[platform_id]
        can_fulfill_all = len(lines) == len(basket_items)
        if can_fulfill_all:
            subtotal = sum((price * qty for _, qty, price in lines), Decimal("0.00"))
            fee = _platform_fee(platform, subtotal)
            single_totals.append(PlatformTotal(
                platform_name=platform.name, can_fulfill_all=True,
                subtotal=subtotal, delivery_fee=fee, total=subtotal + fee,
            ))
        else:
            single_totals.append(PlatformTotal(
                platform_name=platform.name, can_fulfill_all=False,
                subtotal=None, delivery_fee=None, total=None,
            ))

    fulfillable = sorted((t for t in single_totals if t.can_fulfill_all), key=lambda t: t.total)
    best_single = fulfillable[0] if fulfillable else None

    # --- Optimized split: cheapest available platform per item ---
    groups = {}
    for item in basket_items:
        if not item.prices_by_platform:
            continue
        platform_name = item.best_platform
        line_total = item.best_price * item.quantity
        groups.setdefault(platform_name, []).append((item.product.name, item.quantity, item.best_price, line_total))

    split_groups = []
    optimized_total = Decimal("0.00")
    for platform_name, lines in groups.items():
        platform = next((p for p in platform_objs.values() if p.name == platform_name), None)
        subtotal = sum((line[3] for line in lines), Decimal("0.00"))
        fee = _platform_fee(platform, subtotal) if platform else Decimal("0.00")
        total = subtotal + fee
        optimized_total += total
        split_groups.append(SplitGroup(platform_name=platform_name, items=lines, subtotal=subtotal, delivery_fee=fee, total=total))
    split_groups.sort(key=lambda g: g.platform_name)

    all_items_priced = all(item.prices_by_platform for item in basket_items)
    savings = (best_single.total - optimized_total) if (best_single and all_items_priced) else None

    recommend_split = bool(
        all_items_priced and len(split_groups) > 1 and savings is not None and savings >= MIN_SPLIT_SAVINGS
    )

    # --- Explanation: per-item savings supporting the recommendation ---
    explanation = []
    reference_platform = split_groups[0].platform_name if (recommend_split and len(split_groups) == 1) else (
        best_single.platform_name if best_single else None
    )
    for item in basket_items:
        if not item.prices_by_platform or len(item.prices_by_platform) < 2:
            continue
        prices = sorted(item.prices_by_platform.values())
        item_savings = prices[-1] - prices[0]
        if item_savings > 0:
            explanation.append(
                f"\u20b9{item_savings:.0f} cheaper on {item.product.name} on {item.best_platform}"
            )

    return BasketResult(
        items=basket_items, locality=locality,
        single_platform_totals=sorted(single_totals, key=lambda t: (t.total is None, t.total)),
        best_single_platform=best_single,
        optimized_split=split_groups, optimized_total=optimized_total if all_items_priced else None,
        recommend_split=recommend_split, savings_vs_single=savings,
        explanation=explanation[:6],
    )
