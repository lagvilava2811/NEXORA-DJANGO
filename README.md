# NEXORA

NEXORA is a premium, multilingual Django technology store for Georgian, English, and Russian shoppers. The deliverable includes a server-rendered storefront, verified local product media, catalogue search and filters, product comparison, wishlists, cart and checkout, customer accounts, an accessible product guide, and a complete Django administration surface.

## What is included

- Django 5.2 application with Georgian (`/`), English (`/en/`), and Russian (`/ru/`) routes
- 1,000 published real technology model records after the catalogue sync is applied
- One unique, locally stored primary image per published product
- Wikimedia Commons source, author, licence, checksum, and verification metadata
- Category, brand, variant, specification, stock, pricing, review, coupon, address, order, wishlist, and comparison models
- Server-authoritative totals and transactional stock updates
- Dark and light themes, cinematic local video, reduced-motion support, responsive layouts, and visible keyboard focus
- Product JSON-LD, canonical URLs, Open Graph metadata, sitemap, robots policy, and local favicon
- Production security headers, environment-based secrets, PostgreSQL support, WhiteNoise, Docker, and deployment checks

## Quick start on Windows

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.lock
$env:DJANGO_DEBUG = "True"
$env:DJANGO_SECRET_KEY = "replace-this-with-a-private-local-development-secret"
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Open `http://127.0.0.1:8000/`. The administration is at `http://127.0.0.1:8000/admin/`.

The supplied final archive includes the verified catalogue database and media, so a catalogue import is not required for normal use.

For any shared or production environment, set `DJANGO_DEBUG=False` and use a unique, private `DJANGO_SECRET_KEY`. The application now fails closed when that key is missing.

## Catalogue rebuild

The catalogue is built from exact Wikidata item classes and Wikimedia Commons media, not generic search-result thumbnails. The command stages and verifies every file before changing the database:

```powershell
python manage.py sync_wikidata_catalog --target 1000 --workers 4
python manage.py sync_wikidata_catalog --target 1000 --workers 4 --apply --replace --prune-unreferenced
```

Publication requires an active product, active status, a verified local primary image, provenance metadata, a unique SHA-256 digest, and a product/model match. Failed imports leave the current storefront catalogue untouched. See [media/PRODUCT_IMAGE_CONTRACT.md](media/PRODUCT_IMAGE_CONTRACT.md).

## Verification

```powershell
python manage.py migrate --check
python manage.py check
python manage.py check --deploy
python manage.py test
python manage.py collectstatic --noinput
python -m pip check
```

`check --deploy` intentionally reports development-only warnings if it is run with `DJANGO_DEBUG=True`. Run the production check with the environment from `.env.example` and a private secret.

## Email verification

New accounts remain inactive until the owner enters the six-digit code delivered by email or follows the unique one-time verification link in the same message. Codes and link tokens are generated with Python's `secrets` module, stored only as password hashes, expire after ten minutes by default, and are protected by attempt limits, resend cooldowns, and an hourly send cap. Failed SMTP delivery rolls account creation back instead of creating an unverifiable active account.

Production uses Django's SMTP backend. Configure `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS`, and `DEFAULT_FROM_EMAIL` from deployment secrets; never place SMTP credentials in source control. The console backend is suitable only for explicit local development. Verification email and page copy support Georgian, English, and Russian routes.

Signup and verification-recovery throttles use Django's cache and can be tuned with the six `SIGNUP_RATE_LIMIT_*` and `VERIFICATION_RECOVERY_RATE_LIMIT_*` environment variables in `.env.example`. Django's local-memory cache is used only for development and tests. Production requires a shared Redis cache configured as `DJANGO_CACHE_URL=redis://cache:6379/1` (use `rediss://` when the provider requires TLS), so every worker enforces the same counters; startup fails closed when this value is missing.

## Account hardening

Customer sign-in, Django admin sign-in, and password-reset requests are throttled through the shared cache by both IP address and normalized account identifier. Their limits are configurable with `LOGIN_RATE_LIMIT_*`, `ADMIN_LOGIN_RATE_LIMIT_*`, and `PASSWORD_RESET_RATE_LIMIT_*` environment variables. Password resets use a hashed six-digit code that expires after ten minutes by default and return the same confirmation page whether or not the requested email exists.

`X-Forwarded-For` is ignored unless the direct peer belongs to an explicitly configured `DJANGO_TRUSTED_PROXY_IPS` IP/CIDR allowlist. Populate that setting only with a reverse proxy you control and have configured to sanitize forwarded headers; otherwise rate limiting safely uses `REMOTE_ADDR`.

Coupons support a global limit and an optional per-authenticated-customer limit. Set `max_uses_per_user` to `0` for an unrestricted promotion or a positive value for a one-time/limited customer promotion. Product videos are allowlisted by extension, supplied MIME type, and container signature before an admin form accepts them.

## Production configuration

Copy `.env.example` values into the deployment environment. Never commit the production secret. PostgreSQL is recommended through `DATABASE_URL`; SQLite remains convenient for the self-contained local demonstration.

```text
DJANGO_DEBUG=False
DJANGO_SECRET_KEY=<long-random-secret>
DJANGO_ALLOWED_HOSTS=shop.example.com
DJANGO_CSRF_TRUSTED_ORIGINS=https://shop.example.com
DATABASE_URL=postgresql://user:password@db:5432/nexora
POSTGRES_SSLMODE=require
```

For Docker:

```powershell
Copy-Item .env.example .env
# Replace POSTGRES_PASSWORD (use URL-safe characters) and DJANGO_SECRET_KEY in .env before starting.
docker compose up --build
```

The Compose stack starts Django, PostgreSQL 17, and Redis 7.4 with named
volumes for database, cache, and uploaded media. `docker compose down` keeps
those volumes; `docker compose down --volumes` intentionally deletes them.
The web container waits for healthy PostgreSQL and Redis services and exposes
its own health check. Worker/thread counts are configurable with
`WEB_CONCURRENCY`, `GUNICORN_THREADS`, and `GUNICORN_TIMEOUT`.

Dependencies are declared in `requirements.in` and resolved to exact versions
in `requirements.lock`. Runtime, Docker, and CI install only the lock file.
Regenerate it deliberately with:

```powershell
python -m pip install "pip-tools==7.5.2"
python -m piptools compile --output-file=requirements.lock requirements.in
```

GitHub Actions runs the Django tests against PostgreSQL and Redis on every
push/PR, then runs a separate production-like `check --deploy` and static
collection job using non-secret CI-only values. Linux hosts can configure local
SMTP and Gemini credentials with `scripts/configure_gmail_smtp.sh` and
`scripts/configure_gemini_key.sh`; the values are written only to `.env`.

Terminate TLS at a trusted reverse proxy and retain the configured forwarded-protocol header. The included checkout is intentionally a demonstration flow with server-side order creation and no external card/payment provider.

The public `/health/` readiness probe checks database and shared-cache access without exposing exception or topology details. Optional Sentry reporting, structured JSON logging, legal contact details, and support email are configured only through environment variables. Authenticated customers can download their account data and submit or cancel an account-deletion request; fulfillment remains an audited operator action so order records are not silently destroyed.

## Media and archive policy

Product media is intentionally local so pages do not depend on expiring third-party URLs. Source URLs remain as attribution records only. The final archive excludes virtual environments, bytecode, test caches, staging downloads, secrets, and generated static output. Do not remove `media/product_uploads/` or the included database from the self-contained local build.

## Documentation

- [PRODUCT.md](PRODUCT.md) — product requirements and release standard
- [DESIGN.md](DESIGN.md) — design system and interaction rules
- [media/PRODUCT_IMAGE_CONTRACT.md](media/PRODUCT_IMAGE_CONTRACT.md) — publication and provenance contract
