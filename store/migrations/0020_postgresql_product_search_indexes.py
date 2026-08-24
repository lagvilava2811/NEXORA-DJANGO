from django.db import migrations


def create_postgresql_search_indexes(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
        cursor.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS store_product_search_fts_gin "
            "ON store_product USING GIN "
            "(to_tsvector('simple'::regconfig, COALESCE(search_document, ''::text)))"
        )
        cursor.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS store_product_search_trgm_gin "
            "ON store_product USING GIN (search_document gin_trgm_ops)"
        )


def drop_postgresql_search_indexes(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("DROP INDEX CONCURRENTLY IF EXISTS store_product_search_fts_gin")
        cursor.execute("DROP INDEX CONCURRENTLY IF EXISTS store_product_search_trgm_gin")


class Migration(migrations.Migration):
    atomic = False
    dependencies = [("store", "0019_backfill_product_search_document")]

    operations = [
        migrations.RunPython(
            create_postgresql_search_indexes,
            drop_postgresql_search_indexes,
        ),
    ]
