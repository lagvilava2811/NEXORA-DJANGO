from django.conf import settings
from django.core.checks import Error, Tags, register


INSECURE_EMAIL_BACKENDS = ('console', 'locmem', 'dummy', 'filebased')


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

    backend = str(getattr(settings, 'EMAIL_BACKEND', '')).casefold()
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
    return errors
