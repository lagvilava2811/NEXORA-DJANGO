from django.db import migrations


def publish_verified_products(apps, schema_editor):
    Product = apps.get_model("store", "Product")
    ProductMedia = apps.get_model("store", "ProductMedia")
    verified_ids = ProductMedia.objects.filter(
        media_type="image",
        is_primary=True,
        is_verified=True,
        image_file__isnull=False,
    ).exclude(image_file="").values_list("product_id", flat=True)
    Product.objects.filter(
        id__in=verified_ids,
        is_active=True,
        status="active",
    ).update(is_published=True)


def unpublish_products(apps, schema_editor):
    apps.get_model("store", "Product").objects.update(is_published=False)


class Migration(migrations.Migration):
    dependencies = [("store", "0008_catalog_publication_integrity")]
    operations = [migrations.RunPython(publish_verified_products, unpublish_products)]