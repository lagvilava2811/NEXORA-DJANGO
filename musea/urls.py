from django.conf import settings
from django.conf.urls.static import static
from django.conf.urls.i18n import i18n_patterns
from django.contrib import admin
from django.urls import include, path

from .health import live, ready


urlpatterns = [
    path("health/live/", live, name="health_live"),
    path("health/ready/", ready, name="health_ready"),
    path("i18n/", include("django.conf.urls.i18n")),
] + i18n_patterns(
    path("admin/", admin.site.urls),
    path("", include("store.urls")),
    prefix_default_language=False,
)

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.BASE_DIR / "static")
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
