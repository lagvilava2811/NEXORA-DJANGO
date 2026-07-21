from django.conf import settings
from django.db import migrations, models
from django.db.models import Count
from django.db.models.functions import Lower


INDEX_NAME = 'auth_user_email_ci_unique'


def mark_pending_verifications(apps, schema_editor):
    Verification = apps.get_model('store', 'EmailVerification')
    Verification.objects.filter(
        verified_at__isnull=True,
        user__is_active=False,
    ).update(pending_verification_at=models.F('created_at'))


def add_email_unique_index(apps, schema_editor):
    app_label, model_name = settings.AUTH_USER_MODEL.split('.')
    User = apps.get_model(app_label, model_name)
    duplicates = (
        User.objects.exclude(email='')
        .annotate(normalized_email=Lower('email'))
        .values('normalized_email')
        .annotate(total=Count('pk'))
        .filter(total__gt=1)
    )
    if duplicates.exists():
        raise RuntimeError('Duplicate case-insensitive user emails must be resolved before migration')
    if schema_editor.connection.vendor not in {'sqlite', 'postgresql'}:
        raise RuntimeError('Case-insensitive email uniqueness supports SQLite and PostgreSQL')
    quote = schema_editor.quote_name
    table = quote(User._meta.db_table)
    index = quote(INDEX_NAME)
    email = quote('email')
    schema_editor.execute(
        f'CREATE UNIQUE INDEX {index} ON {table} (LOWER({email})) WHERE {email} <> \'\''
    )


def drop_email_unique_index(apps, schema_editor):
    schema_editor.execute(f'DROP INDEX IF EXISTS {schema_editor.quote_name(INDEX_NAME)}')


class Migration(migrations.Migration):
    dependencies = [
        ('store', '0011_productrating'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='emailverification',
            name='pending_verification_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.RunPython(mark_pending_verifications, migrations.RunPython.noop),
        migrations.RunPython(add_email_unique_index, drop_email_unique_index),
    ]
