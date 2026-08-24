import hashlib
import ipaddress

from django.conf import settings
from django.core.cache import cache


def normalize_email(value):
    return (value or '').strip().casefold()


def _parsed_ip(value):
    """Return a canonical IP string, rejecting malformed forwarded values."""
    try:
        return str(ipaddress.ip_address(str(value or '').strip()))
    except ValueError:
        return None


def _trusted_proxy_networks():
    networks = []
    for value in getattr(settings, 'TRUSTED_PROXY_IPS', ()):
        try:
            networks.append(ipaddress.ip_network(str(value).strip(), strict=False))
        except ValueError:
            continue
    return networks


def _is_trusted_proxy(value, networks):
    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        return False
    return any(address in network for network in networks)


def request_ip(request):
    """Resolve the client IP without blindly trusting spoofable proxy headers.

    ``X-Forwarded-For`` is considered only when the direct peer is in the
    explicitly configured proxy allowlist.  Walking the chain from right to
    left ignores trusted proxy hops and returns the nearest untrusted client.
    """
    remote_addr = _parsed_ip(request.META.get('REMOTE_ADDR'))
    if remote_addr is None:
        return 'unknown'

    trusted_networks = _trusted_proxy_networks()
    if not trusted_networks or not _is_trusted_proxy(remote_addr, trusted_networks):
        return remote_addr

    forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '')
    chain = [_parsed_ip(value) for value in forwarded.split(',')]
    chain = [value for value in chain if value]
    for candidate in reversed(chain):
        if not _is_trusted_proxy(candidate, trusted_networks):
            return candidate
    return chain[0] if chain else remote_addr


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
