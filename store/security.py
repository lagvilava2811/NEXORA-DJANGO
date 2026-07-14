import hashlib

from django.core.cache import cache


def normalize_email(value):
    return (value or '').strip().casefold()


def request_ip(request):
    return request.META.get('REMOTE_ADDR') or 'unknown'


def cache_rate_limited(scope, identifier, limit, window_seconds):
    limit = max(1, int(limit))
    window_seconds = max(1, int(window_seconds))
    identity_hash = hashlib.sha256(str(identifier).encode('utf-8')).hexdigest()
    key = f'nexora:rate:{scope}:{identity_hash}'
    if cache.add(key, 1, timeout=window_seconds):
        return False
    try:
        attempts = cache.incr(key)
    except ValueError:
        cache.set(key, 1, timeout=window_seconds)
        return False
    return attempts > limit


def login_rate_limited(request, scope, identifier, *, ip_limit, account_limit, window_seconds):
    """Throttle sign-in style endpoints by both network and account identity."""
    normalized_identifier = normalize_email(identifier)
    limited_by_ip = cache_rate_limited(f'{scope}-ip', request_ip(request), ip_limit, window_seconds)
    limited_by_account = cache_rate_limited(
        f'{scope}-account', normalized_identifier or 'blank', account_limit, window_seconds,
    )
    return limited_by_ip or limited_by_account
