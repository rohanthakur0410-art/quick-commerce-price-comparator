import logging

from django.db.models import Q
from rest_framework import status
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Locality, PriceHistory, Platform, Product
from .serializers import (
    BasketItemInputSerializer,
    BasketResultSerializer,
    ComparisonResultSerializer,
    LocalitySerializer,
    PlatformSerializer,
    PriceHistorySerializer,
    PriceInsightsSerializer,
    ProductDetailSerializer,
    ProductListSerializer,
)
from .services import compare_basket, compare_prices, compute_price_insights

logger = logging.getLogger("products")


def _resolve_locality(request):
    locality_id = request.query_params.get("locality") or request.data.get("locality_id")
    if not locality_id:
        return None, None
    try:
        return Locality.objects.select_related("city__district__state").get(pk=locality_id), None
    except (Locality.DoesNotExist, ValueError):
        return None, Response({"detail": f"No locality found with id={locality_id}."}, status=status.HTTP_404_NOT_FOUND)


class ProductListView(ListAPIView):
    """GET /api/products/?search=milk&locality=<id>

    Search matches product name, brand, category, or subcategory
    (case-insensitive substring), backed by DB indexes - never a Python
    -side scan of the full catalog. Paginated (DRF PageNumberPagination),
    which also bounds how many products get their price materialized
    per request (see products/pricing.py).
    """

    serializer_class = ProductListSerializer

    def get_queryset(self):
        queryset = Product.objects.filter(is_active=True).select_related("subcategory__category")
        search_term = self.request.query_params.get("search", "").strip()
        if search_term:
            queryset = queryset.filter(
                Q(name__icontains=search_term)
                | Q(brand__icontains=search_term)
                | Q(subcategory__name__icontains=search_term)
                | Q(subcategory__category__name__icontains=search_term)
            )
        category = self.request.query_params.get("category")
        if category:
            queryset = queryset.filter(subcategory__category__name__iexact=category)
        return queryset

    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        return response

    def get_serializer_context(self):
        context = super().get_serializer_context()
        locality_id = self.request.query_params.get("locality")
        comparisons = {}
        if locality_id:
            try:
                locality = Locality.objects.get(pk=locality_id)
                page = self.paginate_queryset(self.filter_queryset(self.get_queryset())) or []
                for product in page:
                    result = compare_prices(product, locality=locality)
                    comparisons[product.id] = {"lowest_price": result.lowest_price, "best_platform": result.best_platform}
            except Locality.DoesNotExist:
                pass
        context["comparisons"] = comparisons
        return context


class ProductDetailView(RetrieveAPIView):
    queryset = Product.objects.filter(is_active=True).select_related("subcategory__category")
    serializer_class = ProductDetailSerializer


class ProductCompareView(APIView):
    """GET /api/products/<id>/compare/?locality=<id>"""

    def get(self, request, pk):
        try:
            product = Product.objects.get(pk=pk, is_active=True)
        except Product.DoesNotExist:
            return Response({"detail": f"No product found with id={pk}."}, status=status.HTTP_404_NOT_FOUND)

        locality, error = _resolve_locality(request)
        if error:
            return error
        if locality is None:
            return Response({"detail": "A ?locality=<id> query parameter is required."}, status=status.HTTP_400_BAD_REQUEST)

        result = compare_prices(product, locality=locality)
        return Response(ComparisonResultSerializer(result).data)


class ProductHistoryView(ListAPIView):
    """GET /api/products/<id>/history/?locality=<id>"""

    serializer_class = PriceHistorySerializer

    def get_queryset(self):
        queryset = PriceHistory.objects.filter(product_offer__product_id=self.kwargs["pk"]).select_related(
            "product_offer__platform", "product_offer__locality"
        )
        locality_id = self.request.query_params.get("locality")
        if locality_id:
            queryset = queryset.filter(product_offer__locality_id=locality_id)
        return queryset.order_by("-recorded_at")

    def list(self, request, *args, **kwargs):
        try:
            product = Product.objects.get(pk=self.kwargs["pk"])
        except Product.DoesNotExist:
            return Response({"detail": f"No product found with id={self.kwargs['pk']}."}, status=status.HTTP_404_NOT_FOUND)

        locality, error = _resolve_locality(request)
        if error:
            return error

        response = super().list(request, *args, **kwargs)
        insights = compute_price_insights(product, locality=locality)
        response.data["insights"] = PriceInsightsSerializer(insights).data
        return response


class PlatformListView(ListAPIView):
    queryset = Platform.objects.filter(is_active=True)
    serializer_class = PlatformSerializer


class LocalityListView(ListAPIView):
    """GET /api/localities/?q=Koramangala

    Powers the location picker - matches locality name, city name, or
    pincode.
    """

    serializer_class = LocalitySerializer

    def get_queryset(self):
        queryset = Locality.objects.filter(is_active=True).select_related("city__district__state")
        q = self.request.query_params.get("q", "").strip()
        if q:
            queryset = queryset.filter(
                Q(name__icontains=q) | Q(city__name__icontains=q) | Q(pincode__icontains=q)
            )
        return queryset[:50]


class BasketCompareView(APIView):
    """POST /api/basket/compare/
    {"locality_id": 5, "items": [{"product_id": 1, "quantity": 2}, ...]}
    """

    def post(self, request):
        locality, error = _resolve_locality(request)
        if error:
            return error
        if locality is None:
            return Response({"detail": "locality_id is required."}, status=status.HTTP_400_BAD_REQUEST)

        items_serializer = BasketItemInputSerializer(data=request.data.get("items", []), many=True)
        items_serializer.is_valid(raise_exception=True)

        product_ids = [item["product_id"] for item in items_serializer.validated_data]
        products_by_id = {p.id: p for p in Product.objects.filter(id__in=product_ids, is_active=True)}

        missing = [pid for pid in product_ids if pid not in products_by_id]
        if missing:
            return Response({"detail": f"Unknown product id(s): {missing}"}, status=status.HTTP_404_NOT_FOUND)

        items = [(products_by_id[item["product_id"]], item["quantity"]) for item in items_serializer.validated_data]
        result = compare_basket(items, locality)
        return Response(BasketResultSerializer(result).data)
