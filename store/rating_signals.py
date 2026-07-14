from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import ProductRating, Review
from .rating_services import recompute_product_aggregates


@receiver(post_save, sender=ProductRating)
def synchronize_saved_product_rating(sender, instance, raw=False, **kwargs):
    if raw:
        return
    Review.objects.filter(
        product_id=instance.product_id,
        user_id=instance.user_id,
    ).exclude(rating=instance.rating).update(rating=instance.rating)
    recompute_product_aggregates(instance.product_id)


@receiver(post_delete, sender=ProductRating)
def recompute_after_product_rating_delete(sender, instance, **kwargs):
    recompute_product_aggregates(instance.product_id)


@receiver(post_save, sender=Review)
def synchronize_saved_review(sender, instance, raw=False, **kwargs):
    if raw:
        return
    ProductRating.objects.update_or_create(
        product_id=instance.product_id,
        user_id=instance.user_id,
        defaults={'rating': instance.rating},
    )
    recompute_product_aggregates(instance.product_id)


@receiver(post_delete, sender=Review)
def recompute_after_review_delete(sender, instance, **kwargs):
    recompute_product_aggregates(instance.product_id)
