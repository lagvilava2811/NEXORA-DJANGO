from django.conf import settings
from django.db import models

from .catalog import Product


class UserAddress(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="addresses")
    title = models.CharField(max_length=50, default="Home")
    full_name = models.CharField(max_length=120)
    phone = models.CharField(max_length=30)
    city = models.CharField(max_length=80, default="Tbilisi")
    address_line = models.TextField()
    postal_code = models.CharField(max_length=20, blank=True)
    is_default = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.user.username} - {self.title}"


class Wishlist(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="wishlists")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="wishlisted_by")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "product")

    def __str__(self):
        return f"{self.user.username} → {self.product.name}"


class CompareList(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="compare_lists")
    products = models.ManyToManyField(Product, related_name="in_comparisons")
    created_at = models.DateTimeField(auto_now_add=True)

