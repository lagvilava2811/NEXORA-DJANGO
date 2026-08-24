from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("store", "0016_passwordresetcode"),
    ]

    operations = [
        migrations.CreateModel(
            name="AccountDeletionRequest",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("status", models.CharField(choices=[("pending", "Pending"), ("cancelled", "Cancelled"), ("completed", "Completed")], default="pending", max_length=10)),
                ("requested_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("admin_note", models.TextField(blank=True)),
                ("user", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="deletion_request", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ("-requested_at",)},
        ),
    ]
