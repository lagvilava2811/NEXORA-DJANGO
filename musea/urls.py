from django.conf.urls.i18n import i18n_patterns
from django.contrib import admin
from django.urls import include, path, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.views.static import serve
from store.ops import health_check

urlpatterns = [
    path("health/", health_check, name="health"),
    path("i18n/", include("django.conf.urls.i18n")),
] + i18n_patterns(
    path("admin/", admin.site.urls),
    path("", include("store.urls")),
    prefix_default_language=False,
)
urlpatterns += static(settings.STATIC_URL, document_root=settings.BASE_DIR / "static")
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# The public Render demonstration packages its verified catalogue media inside
# the container. Django's static() helper intentionally becomes a no-op when
# DEBUG=False, therefore public demo media is explicitly served here.
# A full production deployment should move uploaded media to object storage/CDN.
urlpatterns += [
    re_path(r"^media/(?P<path>.*)$", serve, {"document_root": settings.MEDIA_ROOT}),
]
