from unittest.mock import patch

from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase, TestCase
from django.urls import reverse


class HealthEndpointTests(TestCase):
    def test_liveness_does_not_touch_external_dependencies(self):
        response = self.client.get(reverse("health_live"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})
        self.assertEqual(response.headers["Cache-Control"], "no-store")

    def test_readiness_reports_database_and_cache(self):
        response = self.client.get(reverse("health_ready"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"status": "ready", "checks": {"database": "ok", "cache": "ok"}},
        )

    @patch("musea.health.connection.cursor", side_effect=RuntimeError("database unavailable"))
    def test_readiness_fails_closed_without_leaking_exception_details(self, _cursor):
        response = self.client.get(reverse("health_ready"))

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["status"], "unavailable")
        self.assertEqual(response.json()["checks"]["database"], "failed")
        self.assertNotContains(response, "database unavailable", status_code=503)


class MediaStorageConfigurationTests(SimpleTestCase):
    def test_local_storage_remains_the_safe_development_default(self):
        from musea.storage import media_storage_settings

        storage, media_url = media_storage_settings({})

        self.assertEqual(storage["BACKEND"], "django.core.files.storage.FileSystemStorage")
        self.assertEqual(media_url, "/media/")

    def test_s3_storage_requires_a_bucket(self):
        from musea.storage import media_storage_settings

        with self.assertRaisesMessage(ImproperlyConfigured, "AWS_STORAGE_BUCKET_NAME"):
            media_storage_settings({"DJANGO_MEDIA_BACKEND": "s3"})

    def test_s3_storage_supports_r2_and_custom_domains(self):
        from musea.storage import media_storage_settings

        storage, media_url = media_storage_settings(
            {
                "DJANGO_MEDIA_BACKEND": "s3",
                "AWS_STORAGE_BUCKET_NAME": "nexora-media",
                "AWS_S3_ENDPOINT_URL": "https://account.r2.cloudflarestorage.com",
                "AWS_S3_CUSTOM_DOMAIN": "media.nexora.example",
                "AWS_S3_REGION_NAME": "auto",
            }
        )

        self.assertEqual(storage["BACKEND"], "storages.backends.s3.S3Storage")
        self.assertEqual(storage["OPTIONS"]["bucket_name"], "nexora-media")
        self.assertEqual(storage["OPTIONS"]["endpoint_url"], "https://account.r2.cloudflarestorage.com")
        self.assertEqual(storage["OPTIONS"]["region_name"], "auto")
        self.assertEqual(media_url, "https://media.nexora.example/")
