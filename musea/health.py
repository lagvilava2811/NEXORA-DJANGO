from django.core.cache import cache
from django.db import connection
from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET


@require_GET
@never_cache
def live(request):
    """Process liveness probe; deliberately avoids external dependencies."""
    return JsonResponse({"status": "ok"})


@require_GET
@never_cache
def ready(request):
    """Readiness probe for dependencies required to serve real traffic."""
    checks = {"database": "failed", "cache": "failed"}

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        checks["database"] = "ok"
    except Exception:
        pass

    cache_key = "nexora:health:ready"
    try:
        cache.set(cache_key, "ok", timeout=10)
        if cache.get(cache_key) == "ok":
            checks["cache"] = "ok"
        cache.delete(cache_key)
    except Exception:
        pass

    is_ready = all(value == "ok" for value in checks.values())
    return JsonResponse(
        {"status": "ready" if is_ready else "unavailable", "checks": checks},
        status=200 if is_ready else 503,
    )
