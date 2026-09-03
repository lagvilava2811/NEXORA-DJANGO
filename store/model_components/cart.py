from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from .catalog import Product
from .product_details import ProductVariant


class Cart(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="cart")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Cart for {self.user}"


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="cart_items")
    variant = models.ForeignKey(ProductVariant, on_delete=models.CASCADE, null=True, blank=True, related_name="cart_items")
    quantity = models.PositiveSmallIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(quantity__gte=1, quantity__lte=20), name="cart_item_quantity_between_1_and_20"),
            models.UniqueConstraint(fields=("cart", "product"), condition=models.Q(variant__isnull=True), name="unique_cart_product_without_variant"),
            models.UniqueConstraint(fields=("cart", "product", "variant"), condition=models.Q(variant__isnull=False), name="unique_cart_product_variant"),
        ]

    def clean(self):
        if self.variant_id and self.variant.product_id != self.product_id:
            raise ValidationError("The selected variant must belong to the cart product.")

    def __str__(self):
        return f"{self.cart.user} · {self.product} × {self.quantity}"

