import logging

from django.core.cache import cache
from django.db import connection
from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET


logger = logging.getLogger("store.health")


@never_cache
@require_GET
def health_check(request):
    """Readiness probe for the database and shared cache.

    It deliberately returns no exception messages, credentials, hostnames, or
    other topology details to unauthenticated callers.
    """

    checks = {"database": False, "cache": False}
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            checks["database"] = cursor.fetchone() == (1,)
    except Exception:
        logger.exception("health dependency failed", extra={"dependency": "database"})

    try:
        probe_key = "nexora:health:probe"
        cache.set(probe_key, "ok", timeout=10)
        checks["cache"] = cache.get(probe_key) == "ok"
        cache.delete(probe_key)
    except Exception:
        logger.exception("health dependency failed", extra={"dependency": "cache"})

    ready = all(checks.values())
    response = JsonResponse({"status": "ok" if ready else "unavailable", "checks": checks}, status=200 if ready else 503)
    response["Cache-Control"] = "no-store"
    return response
