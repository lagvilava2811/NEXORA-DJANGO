from django.conf import settings
from django.db import models
from django.utils import timezone

from .catalog import Product
from .product_details import ProductVariant
from .promotions import Coupon, GiftCard


class Order(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="orders")
    coupon = models.ForeignKey(Coupon, on_delete=models.SET_NULL, null=True, blank=True, related_name="orders")
    gift_card = models.ForeignKey(GiftCard, on_delete=models.SET_NULL, null=True, blank=True)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    reference = models.CharField(max_length=16, unique=True)
    full_name = models.CharField(max_length=120)
    email = models.EmailField()
    phone = models.CharField(max_length=30, blank=True)
    address = models.TextField()
    city = models.CharField(max_length=80, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    shipping_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=10, decimal_places=2)
    STATUS_CHOICES = (("pending", "Pending"), ("confirmed", "Confirmed"), ("processing", "Processing"), ("shipped", "Shipped"), ("delivered", "Delivered"), ("cancelled", "Cancelled"), ("refunded", "Refunded"))
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="pending")
    PAYMENT_CHOICES = (("pending", "Pending"), ("paid", "Paid"), ("failed", "Failed"), ("refunded", "Refunded"))
    payment_status = models.CharField(max_length=10, choices=PAYMENT_CHOICES, default="pending")
    payment_method = models.CharField(max_length=50, blank=True)
    payment_id = models.CharField(max_length=255, blank=True)
    tracking_number = models.CharField(max_length=100, blank=True)
    shipping_carrier = models.CharField(max_length=50, blank=True)
    estimated_delivery = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.reference


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    variant = models.ForeignKey(ProductVariant, on_delete=models.SET_NULL, null=True, blank=True)
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)

    @property
    def line_total(self):
        return self.unit_price * self.quantity


class ReturnRequest(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="returns")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    REASON_CHOICES = (("defective", "Defective Product"), ("wrong_item", "Wrong Item Received"), ("changed_mind", "Changed Mind"), ("not_as_described", "Not as Described"), ("other", "Other"))
    reason = models.CharField(max_length=20, choices=REASON_CHOICES)
    description = models.TextField()
    STATUS_CHOICES = (("pending", "Pending"), ("approved", "Approved"), ("rejected", "Rejected"), ("completed", "Completed"))
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="pending")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Return #{self.id} for {self.order.reference}"


class WarrantyClaim(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="warranty_claims")
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    description = models.TextField()
    STATUS_CHOICES = (("pending", "Pending"), ("in_review", "In Review"), ("approved", "Approved"), ("rejected", "Rejected"), ("resolved", "Resolved"))
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="pending")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Warranty #{self.id} - {self.product.name}"

