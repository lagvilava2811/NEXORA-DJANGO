from django.core.management.base import BaseCommand

from store.models import Product, ProductRating, Review
from store.rating_services import recompute_product_aggregates


class Command(BaseCommand):
    help = 'Rebuild product rating and approved-review caches from authoritative rows.'

    def handle(self, *args, **options):
        product_ids = Product.objects.values_list('pk', flat=True).iterator()
        product_count = 0
        for product_id in product_ids:
            recompute_product_aggregates(product_id)
            product_count += 1

        rating_count = ProductRating.objects.count()
        review_count = Review.objects.filter(is_approved=True).count()
        self.stdout.write(self.style.SUCCESS(
            f'Repaired {product_count} products: '
            f'{rating_count} ratings, {review_count} approved reviews.'
        ))
