from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [
        ('store', '0009_publish_verified_products'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='EmailVerification',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code_digest', models.CharField(max_length=128)),
                ('expires_at', models.DateTimeField()),
                ('resend_available_at', models.DateTimeField()),
                ('failed_attempts', models.PositiveSmallIntegerField(default=0)),
                ('send_count', models.PositiveSmallIntegerField(default=0)),
                ('send_window_started_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('verified_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='email_verification', to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ('-created_at',)},
        ),
    ]
