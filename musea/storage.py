from django.core.exceptions import ImproperlyConfigured


def media_storage_settings(env):
    """Build local or S3-compatible media storage without reading secrets eagerly."""
    backend = env.get("DJANGO_MEDIA_BACKEND", "local").strip().lower()
    if backend in {"", "local", "filesystem"}:
        return {"BACKEND": "django.core.files.storage.FileSystemStorage"}, "/media/"
    if backend != "s3":
        raise ImproperlyConfigured("DJANGO_MEDIA_BACKEND must be either 'local' or 's3'")

    bucket_name = env.get("AWS_STORAGE_BUCKET_NAME", "").strip()
    if not bucket_name:
        raise ImproperlyConfigured("AWS_STORAGE_BUCKET_NAME is required for S3 media storage")

    options = {
        "bucket_name": bucket_name,
        "default_acl": None,
        "file_overwrite": False,
        "querystring_auth": False,
        "object_parameters": {"CacheControl": "public, max-age=31536000, immutable"},
    }
    optional_values = {
        "access_key": "AWS_ACCESS_KEY_ID",
        "secret_key": "AWS_SECRET_ACCESS_KEY",
        "endpoint_url": "AWS_S3_ENDPOINT_URL",
        "region_name": "AWS_S3_REGION_NAME",
        "custom_domain": "AWS_S3_CUSTOM_DOMAIN",
    }
    for option, variable in optional_values.items():
        value = env.get(variable, "").strip()
        if value:
            options[option] = value

    custom_domain = options.get("custom_domain")
    media_url = f"https://{custom_domain.strip('/')}/" if custom_domain else "/media/"
    return {"BACKEND": "storages.backends.s3.S3Storage", "OPTIONS": options}, media_url
