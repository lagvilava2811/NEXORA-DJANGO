from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction
from django.db.models import Avg, Count

from .models import Product, ProductRating, Review


ZERO_RATING = Decimal('0.0')


def recompute_product_aggregates(product_id):
    with transaction.atomic():
        product = Product.objects.select_for_update().filter(pk=product_id).first()
        if product is None:
            return {
                'rating': ZERO_RATING,
                'rating_count': 0,
                'review_count': 0,
            }

        summary = ProductRating.objects.filter(product_id=product_id).aggregate(
            average=Avg('rating'),
            total=Count('pk'),
        )
        rating_count = summary['total'] or 0
        average = ZERO_RATING
        if rating_count:
            average = Decimal(str(summary['average'])).quantize(
                Decimal('0.1'),
                rounding=ROUND_HALF_UP,
            )
        review_count = Review.objects.filter(
            product_id=product_id,
            is_approved=True,
        ).count()
        Product.objects.filter(pk=product_id).update(
            rating=average,
            rating_average=average,
            rating_count=rating_count,
            review_count=review_count,
        )
        return {
            'rating': average,
            'rating_count': rating_count,
            'review_count': review_count,
        }
