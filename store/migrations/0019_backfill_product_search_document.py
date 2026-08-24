from django.db import migrations


SEARCH_FIELDS = (
    "name",
    "name_ka",
    "name_en",
    "name_ru",
    "brand",
    "sku",
    "short_description",
    "full_description",
    "description",
)


def backfill_search_documents(apps, schema_editor):
    Product = apps.get_model("store", "Product")
    batch = []
    for product in Product.objects.all().iterator(chunk_size=500):
        product.search_document = " ".join(
            str(getattr(product, field, "")).strip()
            for field in SEARCH_FIELDS
            if getattr(product, field, "")
        )
        batch.append(product)
        if len(batch) == 500:
            Product.objects.bulk_update(batch, ("search_document",), batch_size=500)
            batch.clear()
    if batch:
        Product.objects.bulk_update(batch, ("search_document",), batch_size=500)


class Migration(migrations.Migration):
    dependencies = [("store", "0018_product_search_document_cart_cartitem")]

    operations = [
        migrations.RunPython(backfill_search_documents, migrations.RunPython.noop),
    ]
