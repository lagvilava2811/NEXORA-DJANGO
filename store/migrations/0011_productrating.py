from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def clear_legacy_rating_cache(apps, schema_editor):
    Product = apps.get_model('store', 'Product')
    Product.objects.update(rating=0, rating_average=0)


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('store', '0010_emailverification'),
    ]

    operations = [
        migrations.AlterField(
            model_name='product',
            name='rating',
            field=models.DecimalField(decimal_places=1, default=0, max_digits=2),
        ),
        migrations.AlterField(
            model_name='product',
            name='rating_average',
            field=models.DecimalField(decimal_places=1, default=0, max_digits=2),
        ),
        migrations.CreateModel(
            name='ProductRating',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('rating', models.PositiveSmallIntegerField(choices=[(1, 1), (2, 2), (3, 3), (4, 4), (5, 5)])),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('product', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='ratings', to='store.product')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='product_ratings', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ('-updated_at',),
                'constraints': [
                    models.UniqueConstraint(fields=('product', 'user'), name='unique_product_rating_per_user'),
                    models.CheckConstraint(condition=models.Q(('rating__gte', 1), ('rating__lte', 5)), name='product_rating_between_1_and_5'),
                ],
            },
        ),
        migrations.RunPython(clear_legacy_rating_cache, migrations.RunPython.noop),
    ]
