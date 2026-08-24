from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from uuid import uuid4

from django.db import transaction
from django.utils import timezone

from .models import Cart, CartItem, Coupon, Order, OrderItem, Product, ProductVariant

FREE_SHIPPING_THRESHOLD = Decimal("250.00")
STANDARD_SHIPPING = Decimal("20.00")
MONEY = Decimal("0.01")
MAX_CART_QUANTITY = 20


class CheckoutError(Exception):
    pass


@dataclass(frozen=True)
class CartLine:
    product: Product
    variant: ProductVariant | None
    quantity: int
    line_total: Decimal

    @property
    def unit_price(self):
        return self.variant.effective_price if self.variant else self.product.price

    @property
    def key(self):
        return f"{self.product.pk}:{self.variant.pk}" if self.variant else str(self.product.pk)

    @property
    def available_stock(self):
        if self.variant:
            return min(self.product.stock, self.variant.stock_quantity)
        return self.product.stock


def safe_quantity(value, default=1, maximum=MAX_CART_QUANTITY):
    try:
        quantity = int(value)
    except (TypeError, ValueError):
        quantity = default
    return max(0, min(quantity, maximum))


def normalised_bag(session):
    raw = session.get("bag", {})
    if not isinstance(raw, dict):
        return {}
    bag = {}
    for key, value in raw.items():
        try:
            parts = str(key).split(":", 1)
            product_id = int(parts[0])
            variant_id = int(parts[1]) if len(parts) == 2 and parts[1] else None
        except (TypeError, ValueError):
            continue
        quantity = safe_quantity(value, default=0)
        if product_id > 0 and quantity > 0:
            bag[(product_id, variant_id)] = quantity
    return bag


def _authenticated(user):
    return bool(user and getattr(user, "is_authenticated", False))


@transaction.atomic
def merge_session_cart(user, session):
    """Merge a guest session bag into the account cart once after sign-in."""
    if not _authenticated(user):
        return None
    guest_bag = normalised_bag(session)
    cart, _ = Cart.objects.get_or_create(user=user)
    cart = Cart.objects.select_for_update().get(pk=cart.pk)
    if not guest_bag:
        return cart

    product_ids = {product_id for product_id, _ in guest_bag}
    variant_ids = {variant_id for _, variant_id in guest_bag if variant_id}
    products = {
        product.pk: product
        for product in Product.objects.published().filter(pk__in=product_ids)
    }
    variants = {
        variant.pk: variant
        for variant in ProductVariant.objects.filter(
            pk__in=variant_ids,
            product_id__in=product_ids,
            is_active=True,
        )
    }
    existing = {
        (item.product_id, item.variant_id): item
        for item in CartItem.objects.select_for_update().filter(cart=cart)
    }
    for (product_id, variant_id), guest_quantity in guest_bag.items():
        product = products.get(product_id)
        variant = variants.get(variant_id) if variant_id else None
        if product is None or (variant_id and (variant is None or variant.product_id != product_id)):
            continue
        available = min(product.stock, variant.stock_quantity) if variant else product.stock
        key = (product_id, variant_id)
        current = existing.get(key)
        quantity = min((current.quantity if current else 0) + guest_quantity, available, MAX_CART_QUANTITY)
        if quantity <= 0:
            continue
        if current:
            current.quantity = quantity
            current.save(update_fields=("quantity", "updated_at"))
        else:
            existing[key] = CartItem.objects.create(
                cart=cart,
                product=product,
                variant=variant,
                quantity=quantity,
            )

    session.pop("bag", None)
    session.modified = True
    return cart


def cart_mapping(session, user=None, *, lock=False):
    if not _authenticated(user):
        return normalised_bag(session)
    cart = merge_session_cart(user, session)
    if lock:
        cart = Cart.objects.select_for_update().get(pk=cart.pk)
    return {
        (product_id, variant_id): quantity
        for product_id, variant_id, quantity in cart.items.values_list(
            "product_id", "variant_id", "quantity"
        )
    }


@transaction.atomic
def change_cart_quantity(session, user, product, variant, quantity, *, increment=False):
    """Mutate either the persistent account cart or the guest session bag."""
    available = min(product.stock, variant.stock_quantity) if variant else product.stock
    quantity = safe_quantity(quantity, default=0)
    if _authenticated(user):
        cart = merge_session_cart(user, session)
        cart = Cart.objects.select_for_update().get(pk=cart.pk)
        item = CartItem.objects.select_for_update().filter(
            cart=cart,
            product=product,
            variant=variant,
        ).first()
        target = (item.quantity if item and increment else 0) + quantity
        target = min(target, available, MAX_CART_QUANTITY)
        if target <= 0:
            if item:
                item.delete()
        elif item:
            item.quantity = target
            item.save(update_fields=("quantity", "updated_at"))
        else:
            CartItem.objects.create(
                cart=cart,
                product=product,
                variant=variant,
                quantity=target,
            )
        return target

    bag = session.get("bag", {}) if isinstance(session.get("bag", {}), dict) else {}
    key = f"{product.pk}:{variant.pk}" if variant else str(product.pk)
    current = safe_quantity(bag.get(key), default=0) if increment else 0
    target = min(current + quantity, available, MAX_CART_QUANTITY)
    if target > 0:
        bag[key] = target
    else:
        bag.pop(key, None)
    session["bag"] = bag
    session.modified = True
    return target


def clear_cart(session, user=None):
    if _authenticated(user):
        CartItem.objects.filter(cart__user=user).delete()
    session.pop("bag", None)
    session.modified = True


def cart_item_count(session, user=None):
    if _authenticated(user):
        cart = merge_session_cart(user, session)
        return sum(cart.items.values_list("quantity", flat=True))
    return sum(normalised_bag(session).values())


def cart_rows(session, user=None, *, lock=False):
    bag = cart_mapping(session, user, lock=lock)
    product_ids = {product_id for product_id, _ in bag}
    variant_ids = {variant_id for _, variant_id in bag if variant_id}
    products = {
        product.pk: product
        for product in Product.objects.storefront().filter(pk__in=product_ids)
    }
    variants = {
        variant.pk: variant
        for variant in ProductVariant.objects.select_related("product").filter(
            pk__in=variant_ids, product_id__in=product_ids, is_active=True
        )
    }
    lines = []
    subtotal = Decimal("0.00")
    for (product_id, variant_id), requested in bag.items():
        product = products.get(product_id)
        variant = variants.get(variant_id) if variant_id else None
        if product is None or product.stock <= 0 or (variant_id and (variant is None or variant.product_id != product_id)):
            continue
        available_stock = min(product.stock, variant.stock_quantity) if variant else product.stock
        if available_stock <= 0:
            continue
        quantity = min(requested, available_stock, MAX_CART_QUANTITY)
        unit_price = variant.effective_price if variant else product.price
        line_total = (unit_price * quantity).quantize(MONEY, rounding=ROUND_HALF_UP)
        lines.append(CartLine(product, variant, quantity, line_total))
        subtotal += line_total
    return lines, subtotal.quantize(MONEY)


def shipping_cost(subtotal):
    return Decimal("0.00") if subtotal >= FREE_SHIPPING_THRESHOLD else STANDARD_SHIPPING


def valid_coupon(coupon_id, subtotal, lock=False, user=None):
    if not coupon_id:
        return None
    queryset = Coupon.objects
    if lock:
        queryset = queryset.select_for_update()
    coupon = queryset.filter(pk=coupon_id).first()
    now = timezone.now()
    if not coupon or not coupon.is_active or coupon.valid_from > now:
        return None
    if coupon.valid_to and coupon.valid_to < now:
        return None
    if coupon.max_uses and coupon.times_used >= coupon.max_uses:
        return None
    if coupon.max_uses_per_user and getattr(user, "is_authenticated", False):
        if Order.objects.filter(coupon=coupon, user=user).count() >= coupon.max_uses_per_user:
            return None
    if subtotal < coupon.min_order_amount:
        return None
    return coupon


def coupon_discount(coupon, subtotal):
    if not coupon:
        return Decimal("0.00")
    if coupon.discount_percent:
        amount = subtotal * Decimal(coupon.discount_percent) / Decimal("100")
    else:
        amount = coupon.discount_amount
    return min(subtotal, amount).quantize(MONEY, rounding=ROUND_HALF_UP)


def cart_totals(session, user=None):
    lines, subtotal = cart_rows(session, user)
    coupon = valid_coupon(session.get("coupon_id"), subtotal, user=user)
    discount = coupon_discount(coupon, subtotal)
    shipping = shipping_cost(subtotal)
    total = (subtotal + shipping - discount).quantize(MONEY)
    return {
        "lines": lines,
        "subtotal": subtotal,
        "shipping": shipping,
        "discount": discount,
        "coupon": coupon,
        "total": total,
    }


@transaction.atomic
def create_order_from_session(session, cleaned_data, user=None):
    bag = cart_mapping(session, user, lock=True)
    if not bag:
        raise CheckoutError("Your bag is empty.")

    product_ids = {product_id for product_id, _ in bag}
    variant_ids = {variant_id for _, variant_id in bag if variant_id}
    products = {
        product.pk: product
        for product in Product.objects.select_for_update().filter(
            pk__in=product_ids,
            is_active=True,
            is_published=True,
            status="active",
        )
    }
    variants = {
        variant.pk: variant
        for variant in ProductVariant.objects.select_for_update().filter(
            pk__in=variant_ids, product_id__in=product_ids, is_active=True
        )
    }
    lines = []
    subtotal = Decimal("0.00")
    for (product_id, variant_id), quantity in bag.items():
        product = products.get(product_id)
        if product is None or not product.has_verified_image:
            raise CheckoutError("A product in your bag is no longer available.")
        variant = variants.get(variant_id) if variant_id else None
        if variant_id and (variant is None or variant.product_id != product_id):
            raise CheckoutError("A selected product option is no longer available.")
        available_stock = min(product.stock, variant.stock_quantity) if variant else product.stock
        if quantity > available_stock:
            raise CheckoutError(f"Only {available_stock} units of {product.name} remain.")
        unit_price = variant.effective_price if variant else product.price
        line_total = (unit_price * quantity).quantize(MONEY)
        lines.append(CartLine(product, variant, quantity, line_total))
        subtotal += line_total

    if not lines:
        raise CheckoutError("Your bag is empty.")

    subtotal = subtotal.quantize(MONEY)
    coupon = valid_coupon(session.get("coupon_id"), subtotal, lock=True, user=user)
    discount = coupon_discount(coupon, subtotal)
    shipping = shipping_cost(subtotal)
    total = (subtotal + shipping - discount).quantize(MONEY)
    order = Order.objects.create(
        reference="NX-" + uuid4().hex[:10].upper(),
        user=user if getattr(user, "is_authenticated", False) else None,
        coupon=coupon,
        full_name=cleaned_data["full_name"],
        email=cleaned_data["email"],
        phone=cleaned_data["phone"],
        address=cleaned_data["address"],
        city=cleaned_data["city"],
        postal_code=cleaned_data.get("postal_code", ""),
        subtotal=subtotal,
        shipping_cost=shipping,
        tax_amount=Decimal("0.00"),
        discount_amount=discount,
        total=total,
        status="pending",
        payment_status="pending",
        payment_method=cleaned_data["payment_method"],
        notes=cleaned_data.get("notes", ""),
    )
    OrderItem.objects.bulk_create(
        [
            OrderItem(
                order=order,
                product=line.product,
                variant=line.variant,
                quantity=line.quantity,
                unit_price=line.unit_price,
            )
            for line in lines
        ]
    )
    for line in lines:
        line.product.stock -= line.quantity
        line.product.save(update_fields=["stock", "updated_at"])
        if line.variant:
            line.variant.stock_quantity -= line.quantity
            line.variant.save(update_fields=["stock_quantity"])
    if coupon:
        coupon.times_used += 1
        coupon.save(update_fields=["times_used"])
    if _authenticated(user):
        CartItem.objects.filter(cart__user=user).delete()
    return order
