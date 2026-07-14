import os
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent


def load_local_env(path):
    """Load simple local development variables without overriding real deployment env."""
    if not path.is_file():
        return
    # utf-8-sig also accepts files created by Windows PowerShell, which adds a BOM.
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key:
            os.environ.setdefault(key, value.strip().strip("\"'"))


load_local_env(BASE_DIR / ".env")
TESTING = 'test' in sys.argv
DEBUG = os.getenv("DJANGO_DEBUG", "False").lower() in {"1", "true", "yes"}
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "")
if not SECRET_KEY:
    raise ImproperlyConfigured("DJANGO_SECRET_KEY must be set in the environment")

ALLOWED_HOSTS = [value.strip() for value in os.getenv("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,testserver").split(",") if value.strip()]
CSRF_TRUSTED_ORIGINS = [value.strip() for value in os.getenv("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",") if value.strip()]

INSTALLED_APPS = [
    "django.contrib.admin", "django.contrib.auth", "django.contrib.contenttypes",
    "django.contrib.sessions", "django.contrib.messages", "django.contrib.staticfiles",
    "django.contrib.humanize", "store",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "store.middleware.SecurityHeadersMiddleware",
    "store.middleware.AdminLoginRateLimitMiddleware",
]
ROOT_URLCONF = "musea.urls"
TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [BASE_DIR / "templates"],
    "APP_DIRS": True,
    "OPTIONS": {"context_processors": [
        "django.template.context_processors.request",
        "django.contrib.auth.context_processors.auth",
        "django.contrib.messages.context_processors.messages",
        "store.context_processors.global_context",
    ]},
}]
WSGI_APPLICATION = "musea.wsgi.application"


def database_from_url(value):
    parsed = urlparse(value)
    if parsed.scheme in {"postgres", "postgresql", "pgsql"}:
        return {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": unquote(parsed.path.lstrip("/")),
            "USER": unquote(parsed.username or ""),
            "PASSWORD": unquote(parsed.password or ""),
            "HOST": parsed.hostname or "localhost",
            "PORT": parsed.port or 5432,
            "CONN_MAX_AGE": 60,
            "OPTIONS": {"sslmode": os.getenv("POSTGRES_SSLMODE", "prefer")},
        }
    if parsed.scheme == "sqlite":
        return {"ENGINE": "django.db.backends.sqlite3", "NAME": unquote(parsed.path)}
    raise RuntimeError("DATABASE_URL must use postgresql:// or sqlite://")


DATABASE_URL = os.getenv("DATABASE_URL", "")
DATABASES = {"default": database_from_url(DATABASE_URL) if DATABASE_URL else {
    "ENGINE": "django.db.backends.sqlite3",
    "NAME": BASE_DIR / "db.sqlite3",
}}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 10}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
LANGUAGE_CODE = "ka"
LANGUAGES = [("ka", "ქართული"), ("en", "English"), ("ru", "Русский")]
USE_I18N = True
TIME_ZONE = "Asia/Tbilisi"
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": ("django.contrib.staticfiles.storage.StaticFilesStorage" if DEBUG or "test" in sys.argv else "whitenoise.storage.CompressedManifestStaticFilesStorage")},
}
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
FILE_UPLOAD_PERMISSIONS = 0o640
FILE_UPLOAD_DIRECTORY_PERMISSIONS = 0o750
DATA_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
LOGIN_URL = "login"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_AGE = 60 * 60 * 24 * 14
CSRF_COOKIE_SAMESITE = "Lax"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
X_FRAME_OPTIONS = "DENY"
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

if not DEBUG:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "NEXORA <noreply@nexora.example>")
DJANGO_CACHE_URL = os.getenv('DJANGO_CACHE_URL', '').strip()
if DJANGO_CACHE_URL:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.redis.RedisCache',
            'LOCATION': DJANGO_CACHE_URL,
        },
    }
elif DEBUG or TESTING:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'nexora-local',
        },
    }
else:
    raise ImproperlyConfigured('DJANGO_CACHE_URL is required when DJANGO_DEBUG=False')
EMAIL_BACKEND = os.getenv(
    'DJANGO_EMAIL_BACKEND',
    'django.core.mail.backends.console.EmailBackend' if DEBUG else 'django.core.mail.backends.smtp.EmailBackend',
)
EMAIL_HOST = os.getenv('EMAIL_HOST', 'localhost')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', '587'))
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD', '')
EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS', 'True').lower() in {'1', 'true', 'yes'}
EMAIL_USE_SSL = os.getenv('EMAIL_USE_SSL', 'False').lower() in {'1', 'true', 'yes'}
EMAIL_TIMEOUT = int(os.getenv('EMAIL_TIMEOUT', '10'))
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '').strip()
GEMINI_MODEL = os.getenv('GEMINI_MODEL', 'gemini-2.5-flash-lite').strip()
GEMINI_ENABLED = os.getenv('GEMINI_ENABLED', 'False').lower() in {'1', 'true', 'yes'}
EMAIL_VERIFICATION_EXPIRY_SECONDS = int(os.getenv('EMAIL_VERIFICATION_EXPIRY_SECONDS', '600'))
EMAIL_VERIFICATION_MAX_ATTEMPTS = int(os.getenv('EMAIL_VERIFICATION_MAX_ATTEMPTS', '5'))
EMAIL_VERIFICATION_RESEND_COOLDOWN = int(os.getenv('EMAIL_VERIFICATION_RESEND_COOLDOWN', '60'))
EMAIL_VERIFICATION_MAX_SENDS_PER_HOUR = int(os.getenv('EMAIL_VERIFICATION_MAX_SENDS_PER_HOUR', '5'))
SIGNUP_RATE_LIMIT_PER_IP = int(os.getenv('SIGNUP_RATE_LIMIT_PER_IP', '10'))
SIGNUP_RATE_LIMIT_PER_EMAIL = int(os.getenv('SIGNUP_RATE_LIMIT_PER_EMAIL', '3'))
SIGNUP_RATE_LIMIT_WINDOW = int(os.getenv('SIGNUP_RATE_LIMIT_WINDOW', '3600'))
VERIFICATION_RECOVERY_RATE_LIMIT_PER_IP = int(os.getenv('VERIFICATION_RECOVERY_RATE_LIMIT_PER_IP', '10'))
VERIFICATION_RECOVERY_RATE_LIMIT_PER_EMAIL = int(os.getenv('VERIFICATION_RECOVERY_RATE_LIMIT_PER_EMAIL', '5'))
VERIFICATION_RECOVERY_RATE_LIMIT_WINDOW = int(os.getenv('VERIFICATION_RECOVERY_RATE_LIMIT_WINDOW', '3600'))
LOGIN_RATE_LIMIT_PER_IP = int(os.getenv('LOGIN_RATE_LIMIT_PER_IP', '10'))
LOGIN_RATE_LIMIT_PER_ACCOUNT = int(os.getenv('LOGIN_RATE_LIMIT_PER_ACCOUNT', '5'))
LOGIN_RATE_LIMIT_WINDOW = int(os.getenv('LOGIN_RATE_LIMIT_WINDOW', '900'))
ADMIN_LOGIN_RATE_LIMIT_PER_IP = int(os.getenv('ADMIN_LOGIN_RATE_LIMIT_PER_IP', '10'))
ADMIN_LOGIN_RATE_LIMIT_PER_ACCOUNT = int(os.getenv('ADMIN_LOGIN_RATE_LIMIT_PER_ACCOUNT', '5'))
ADMIN_LOGIN_RATE_LIMIT_WINDOW = int(os.getenv('ADMIN_LOGIN_RATE_LIMIT_WINDOW', '900'))
PASSWORD_RESET_RATE_LIMIT_PER_IP = int(os.getenv('PASSWORD_RESET_RATE_LIMIT_PER_IP', '5'))
PASSWORD_RESET_RATE_LIMIT_PER_ACCOUNT = int(os.getenv('PASSWORD_RESET_RATE_LIMIT_PER_ACCOUNT', '3'))
PASSWORD_RESET_RATE_LIMIT_WINDOW = int(os.getenv('PASSWORD_RESET_RATE_LIMIT_WINDOW', '3600'))

if EMAIL_USE_TLS and EMAIL_USE_SSL:
    raise RuntimeError('EMAIL_USE_TLS and EMAIL_USE_SSL cannot both be enabled')

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"standard": {"format": "{levelname} {asctime} {name}: {message}", "style": "{"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "standard"}},
    "root": {"handlers": ["console"], "level": os.getenv("DJANGO_LOG_LEVEL", "INFO")},
}
