from django.db import models
from django.utils import timezone


class Coupon(models.Model):
    code = models.CharField(max_length=50, unique=True)
    discount_percent = models.PositiveIntegerField(default=0, help_text="Discount percent (e.g. 10 for 10%)")
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, help_text="Discount amount in currency")
    is_active = models.BooleanField(default=True)
    valid_from = models.DateTimeField(default=timezone.now)
    valid_to = models.DateTimeField(null=True, blank=True)
    min_order_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text="Minimum order amount")
    max_uses = models.PositiveIntegerField(default=0, help_text="0 = unlimited")
    max_uses_per_user = models.PositiveIntegerField(default=0, help_text="0 = unlimited per customer")
    times_used = models.PositiveIntegerField(default=0)

    def __str__(self):
        return self.code

    @property
    def is_valid(self):
        now = timezone.now()
        if not self.is_active:
            return False
        if self.valid_to and now > self.valid_to:
            return False
        if self.max_uses > 0 and self.times_used >= self.max_uses:
            return False
        return True


class GiftCard(models.Model):
    code = models.CharField(max_length=50, unique=True)
    initial_balance = models.DecimalField(max_digits=10, decimal_places=2)
    current_balance = models.DecimalField(max_digits=10, decimal_places=2)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Gift Card {self.code} (₾{self.current_balance})"

