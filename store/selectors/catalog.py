from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from django.db.models import F, Q


SORT_ORDERING = {
    "featured": "-is_featured",
    "price-asc": "price",
    "price-desc": "-price",
    "rating": "-rating",
    "new": "-created_at",
    "name": "name",
}


def _decimal(value, *, maximum=Decimal("1000000")):
    if not value:
        return None
    try:
        parsed = Decimal(value)
    except (InvalidOperation, TypeError, ValueError):
        return None
    return parsed if Decimal("0") <= parsed <= maximum else None


@dataclass(frozen=True, slots=True)
class CatalogFilters:
    query: str = ""
    category: str = ""
    brand: str = ""
    min_price: Decimal | None = None
    max_price: Decimal | None = None
    min_rating: Decimal | None = None
    in_stock: bool = False
    discount: bool = False
    sort: str = "featured"

    @property
    def ordering(self):
        return SORT_ORDERING[self.sort]

    @classmethod
    def from_query(cls, query_params):
        sort = str(query_params.get("sort", "featured"))
        if sort not in SORT_ORDERING:
            sort = "featured"
        return cls(
            query=str(query_params.get("q", "")).strip()[:120],
            category=str(query_params.get("category", "")).strip()[:100],
            brand=str(query_params.get("brand", "")).strip()[:100],
            min_price=_decimal(query_params.get("min_price")),
            max_price=_decimal(query_params.get("max_price")),
            min_rating=_decimal(query_params.get("min_rating"), maximum=Decimal("5")),
            in_stock=query_params.get("in_stock") == "1",
            discount=query_params.get("discount") == "1",
            sort=sort,
        )

    def apply(self, products):
        if self.query:
            products = products.filter(
                Q(name__icontains=self.query)
                | Q(name_ka__icontains=self.query)
                | Q(name_en__icontains=self.query)
                | Q(name_ru__icontains=self.query)
                | Q(description__icontains=self.query)
                | Q(short_description__icontains=self.query)
                | Q(full_description__icontains=self.query)
                | Q(brand__icontains=self.query)
                | Q(sku__icontains=self.query)
            )
        if self.category:
            products = products.filter(category__slug=self.category)
        if self.brand:
            products = products.filter(
                Q(brand__iexact=self.brand)
                | Q(brand_obj__slug=self.brand)
                | Q(brand_obj__name__iexact=self.brand)
            )
        if self.min_price is not None:
            products = products.filter(price__gte=self.min_price)
        if self.max_price is not None:
            products = products.filter(price__lte=self.max_price)
        if self.in_stock:
            products = products.filter(stock__gt=0)
        if self.min_rating is not None:
            products = products.filter(rating__gte=self.min_rating)
        if self.discount:
            products = products.filter(compare_at_price__isnull=False, compare_at_price__gt=F("price"))
        return products.order_by(self.ordering, "name", "pk")
