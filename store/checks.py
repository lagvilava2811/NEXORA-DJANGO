from email.utils import parseaddr

from django.conf import settings
from django.core.checks import Error, Tags, register
from django.core.validators import validate_email
from django.core.exceptions import ValidationError


INSECURE_EMAIL_BACKENDS = ('console', 'locmem', 'dummy', 'filebased')
LOCAL_SMTP_HOSTS = {'localhost', '127.0.0.1', '::1'}


def is_valid_sender(value):
    """Accept a syntactically valid mailbox, optionally with a display name."""
    _, address = parseaddr(str(value or '').strip())
    if not address:
        return False
    try:
        validate_email(address)
    except ValidationError:
        return False
    return not address.casefold().endswith(('.example', '.invalid', '.test'))


@register(Tags.security)
def production_email_configuration(app_configs, **kwargs):
    if settings.DEBUG or getattr(settings, 'TESTING', False):
        return []

    errors = []
    cache_config = getattr(settings, 'CACHES', {}).get('default', {})
    cache_backend = str(cache_config.get('BACKEND', '')).strip()
    cache_location = str(cache_config.get('LOCATION', '')).strip().casefold()
    if (
        cache_backend != 'django.core.cache.backends.redis.RedisCache'
        or not cache_location.startswith(('redis://', 'rediss://'))
    ):
        errors.append(Error(
            'Production signup and verification throttles require a shared Redis cache.',
            id='store.E006',
        ))

    provider = str(getattr(settings, 'NEXORA_EMAIL_PROVIDER', 'smtp')).strip().casefold()
    backend = str(getattr(settings, 'EMAIL_BACKEND', '')).casefold()
    if provider == 'resend':
        if not str(getattr(settings, 'RESEND_API_KEY', '')).strip():
            errors.append(Error(
                'RESEND_API_KEY is required when NEXORA_EMAIL_PROVIDER=resend.',
                id='store.E011',
            ))
        if not is_valid_sender(getattr(settings, 'DEFAULT_FROM_EMAIL', '')):
            errors.append(Error(
                'DEFAULT_FROM_EMAIL must be a real, provider-verified sender address in production.',
                id='store.E010',
            ))
        return errors

    if provider != 'smtp':
        errors.append(Error(
            'NEXORA_EMAIL_PROVIDER must be either smtp or resend.',
            id='store.E012',
        ))
        return errors

    if not backend or any(fragment in backend for fragment in INSECURE_EMAIL_BACKENDS):
        errors.append(Error(
            'Production email verification requires a real delivery backend.',
            id='store.E001',
        ))

    if backend.endswith('smtp.EmailBackend'.casefold()):
        required = (
            ('EMAIL_HOST', 'store.E002'),
            ('EMAIL_HOST_USER', 'store.E003'),
            ('EMAIL_HOST_PASSWORD', 'store.E004'),
            ('DEFAULT_FROM_EMAIL', 'store.E005'),
        )
        for setting_name, error_id in required:
            if not str(getattr(settings, setting_name, '')).strip():
                errors.append(Error(
                    f'{setting_name} is required for production SMTP delivery.',
                    id=error_id,
                ))
        host = str(getattr(settings, 'EMAIL_HOST', '')).strip().casefold()
        if host in LOCAL_SMTP_HOSTS:
            errors.append(Error(
                'EMAIL_HOST must point to an external SMTP provider in production.',
                id='store.E007',
            ))
        port = getattr(settings, 'EMAIL_PORT', None)
        if not isinstance(port, int) or not 1 <= port <= 65535:
            errors.append(Error(
                'EMAIL_PORT must be a valid TCP port for production SMTP delivery.',
                id='store.E008',
            ))
        elif port == 25:
            errors.append(Error(
                'EMAIL_PORT=25 is unsuitable for Render; use your provider\'s TLS port (usually 587 or 465).',
                id='store.E009',
            ))
        if not is_valid_sender(getattr(settings, 'DEFAULT_FROM_EMAIL', '')):
            errors.append(Error(
                'DEFAULT_FROM_EMAIL must be a real, provider-verified sender address in production.',
                id='store.E010',
            ))
    return errors
