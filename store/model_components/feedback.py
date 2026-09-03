from django.conf import settings
from django.db import models

from .catalog import Product


class Review(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="reviews")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reviews")
    rating = models.PositiveIntegerField(choices=[(i, i) for i in range(1, 6)])
    title = models.CharField(max_length=150, blank=True)
    body = models.TextField()
    is_verified_purchase = models.BooleanField(default=False)
    is_approved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("product", "user")

    def __str__(self):
        return f"{self.user.username} → {self.product.name} ({self.rating}★)"


class ProductRating(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='ratings')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='product_ratings')
    rating = models.PositiveSmallIntegerField(choices=[(value, value) for value in range(1, 6)])
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-updated_at',)
        constraints = [
            models.UniqueConstraint(fields=('product', 'user'), name='unique_product_rating_per_user'),
            models.CheckConstraint(condition=models.Q(rating__gte=1, rating__lte=5), name='product_rating_between_1_and_5'),
        ]

    def __str__(self):
        return f'{self.user} → {self.product} ({self.rating}★)'

