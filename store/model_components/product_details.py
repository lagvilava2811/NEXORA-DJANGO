from django.db import models

from .catalog import Category, Product


class ProductVariant(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="variants")
    name = models.CharField(max_length=120)
    sku = models.CharField(max_length=64, unique=True)
    barcode = models.CharField(max_length=64, blank=True)
    color = models.CharField(max_length=40, blank=True)
    storage = models.CharField(max_length=40, blank=True)
    ram = models.CharField(max_length=40, blank=True)
    size = models.CharField(max_length=40, blank=True)
    price_delta = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    compare_at_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    stock_quantity = models.PositiveIntegerField(default=0)
    reserved_quantity = models.PositiveIntegerField(default=0)
    low_stock_threshold = models.PositiveIntegerField(default=5)
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["product", "name"], name="unique_variant_name")]

    @property
    def effective_price(self):
        return self.product.price + self.price_delta

    def __str__(self):
        return f"{self.product.name} · {self.name}"


class TechnicalSpecification(models.Model):
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name="specifications")
    key = models.CharField(max_length=80)
    label_ka = models.CharField(max_length=100)
    label_en = models.CharField(max_length=100)
    label_ru = models.CharField(max_length=100)
    VALUE_TYPE_CHOICES = (("text", "Text"), ("number", "Number"), ("boolean", "Boolean"))
    value_type = models.CharField(max_length=10, choices=VALUE_TYPE_CHOICES, default="text")
    filterable = models.BooleanField(default=True)
    comparable = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.category.name} - {self.label_en}"


class ProductSpecificationValue(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="specification_values")
    variant = models.ForeignKey(ProductVariant, on_delete=models.CASCADE, null=True, blank=True, related_name="specification_values")
    specification = models.ForeignKey(TechnicalSpecification, on_delete=models.CASCADE, related_name="values")
    value = models.CharField(max_length=255)

    def __str__(self):
        return f"{self.product.name} - {self.specification.key}: {self.value}"

