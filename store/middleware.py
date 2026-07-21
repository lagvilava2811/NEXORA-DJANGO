import secrets

from django.conf import settings
from django.http import HttpResponse

from .security import login_rate_limited


class SecurityHeadersMiddleware:
    """Headers not currently emitted by Django's built-in SecurityMiddleware."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.csp_nonce = secrets.token_urlsafe(18)
        response = self.get_response(request)
        # The home-page visualizer can use the microphone after the visitor
        # explicitly grants browser permission.  Set this directly because a
        # reverse proxy or an earlier middleware may have supplied a stricter
        # default header.
        response["Permissions-Policy"] = (
            "camera=(), microphone=(self), geolocation=(), payment=(), usb=(), browsing-topics=()"
        )
        style_policy = "style-src 'self' 'unsafe-inline'" if request.path.startswith("/admin/") else "style-src 'self'"
        response.setdefault(
            "Content-Security-Policy",
            "; ".join(
                (
                    "default-src 'self'",
                    "base-uri 'self'",
                    "connect-src 'self'",
                    "font-src 'self'",
                    "form-action 'self'",
                    "frame-ancestors 'none'",
                    "img-src 'self' data:",
                    "media-src 'self'",
                    "object-src 'none'",
                    f"script-src 'self' 'nonce-{request.csp_nonce}'",
                    style_policy,
                )
            ),
        )
        return response


class AdminLoginRateLimitMiddleware:
    """Apply the same shared-cache brute-force control to Django admin."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method == "POST" and request.path.rstrip("/") == "/admin/login":
            if login_rate_limited(
                request,
                "admin-login",
                request.POST.get("username", ""),
                ip_limit=getattr(settings, "ADMIN_LOGIN_RATE_LIMIT_PER_IP", 10),
                account_limit=getattr(settings, "ADMIN_LOGIN_RATE_LIMIT_PER_ACCOUNT", 5),
                window_seconds=getattr(settings, "ADMIN_LOGIN_RATE_LIMIT_WINDOW", 900),
            ):
                return HttpResponse("Too many sign-in attempts. Please wait and try again.", status=429)
        return self.get_response(request)
