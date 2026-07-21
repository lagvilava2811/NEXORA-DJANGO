from decimal import Decimal, ROUND_HALF_UP

from django.db import migrations, models
from django.db.models import Avg, Count


def backfill_rating_and_review_caches(apps, schema_editor):
    Product = apps.get_model('store', 'Product')
    ProductRating = apps.get_model('store', 'ProductRating')
    Review = apps.get_model('store', 'Review')

    for review in Review.objects.all().iterator():
        vote, created = ProductRating.objects.get_or_create(
            product_id=review.product_id,
            user_id=review.user_id,
            defaults={'rating': review.rating},
        )
        if not created and review.rating != vote.rating:
            Review.objects.filter(pk=review.pk).update(rating=vote.rating)

    for product_id in Product.objects.values_list('pk', flat=True).iterator():
        rating_summary = ProductRating.objects.filter(product_id=product_id).aggregate(
            average=Avg('rating'),
            total=Count('pk'),
        )
        rating_count = rating_summary['total'] or 0
        average = Decimal('0.0')
        if rating_count:
            average = Decimal(str(rating_summary['average'])).quantize(
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


class Migration(migrations.Migration):
    dependencies = [
        ('store', '0012_email_verification_security'),
    ]

    operations = [
        migrations.AddField(
            model_name='product',
            name='rating_count',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.RunPython(
            backfill_rating_and_review_caches,
            migrations.RunPython.noop,
        ),
    ]
