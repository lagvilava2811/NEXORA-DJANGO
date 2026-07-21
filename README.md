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
python -m pip install -r requirements.txt
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

New accounts remain inactive until the owner enters the six-digit code delivered by email. Codes are generated with Python's `secrets` module, stored only as password hashes, expire after ten minutes by default, and are protected by attempt limits, resend cooldowns, and an hourly send cap. Failed SMTP delivery rolls account creation back instead of creating an unverifiable active account.

Production uses Django's SMTP backend. Configure `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS`, and `DEFAULT_FROM_EMAIL` from deployment secrets; never place SMTP credentials in source control. The console backend is suitable only for explicit local development. Verification email and page copy support Georgian, English, and Russian routes.

Signup and verification-recovery throttles use Django's cache and can be tuned with the six `SIGNUP_RATE_LIMIT_*` and `VERIFICATION_RECOVERY_RATE_LIMIT_*` environment variables in `.env.example`. Django's local-memory cache is used only for development and tests. Production requires a shared Redis cache configured as `DJANGO_CACHE_URL=redis://cache:6379/1` (use `rediss://` when the provider requires TLS), so every worker enforces the same counters; startup fails closed when this value is missing.

## Account hardening

Customer sign-in, Django admin sign-in, and password-reset requests are throttled through the shared cache by both IP address and normalized account identifier. Their limits are configurable with `LOGIN_RATE_LIMIT_*`, `ADMIN_LOGIN_RATE_LIMIT_*`, and `PASSWORD_RESET_RATE_LIMIT_*` environment variables. Password resets use Django's signed, expiring reset token and return the same confirmation page whether or not the requested email exists.

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
docker compose up --build
```

Terminate TLS at a trusted reverse proxy and retain the configured forwarded-protocol header. Connect a certified payment provider before accepting online card payments; the included checkout supports a safe cash-on-delivery flow and server-side order creation.

## Media and archive policy

Product media is intentionally local so pages do not depend on expiring third-party URLs. Source URLs remain as attribution records only. The final archive excludes virtual environments, bytecode, test caches, staging downloads, secrets, and generated static output. Do not remove `media/product_uploads/` or the included database from the self-contained local build.

## Documentation

- [PRODUCT.md](PRODUCT.md) — product requirements and release standard
- [DESIGN.md](DESIGN.md) — design system and interaction rules
- [media/PRODUCT_IMAGE_CONTRACT.md](media/PRODUCT_IMAGE_CONTRACT.md) — publication and provenance contract
