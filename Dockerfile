FROM python:3.13-slim-bookworm AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /build
COPY requirements.lock ./
RUN python -m pip wheel --wheel-dir /wheels -r requirements.lock

FROM python:3.13-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8000

RUN addgroup --system nexora && adduser --system --ingroup nexora nexora
WORKDIR /app

COPY --from=builder /wheels /wheels
COPY requirements.lock ./
RUN python -m pip install --no-index --find-links=/wheels -r requirements.lock && \
    rm -rf /wheels

COPY --chown=nexora:nexora . .

# ``WORKDIR`` is created as root.  Create the generated static destination
# before dropping privileges so Django's collectstatic command can write it
# during the image build.
RUN mkdir -p /app/staticfiles && chown -R nexora:nexora /app

USER nexora
# Build the exact same hashed static manifest used at runtime.  Building with
# DEBUG=True creates only unhashed files, while production templates request
# manifest-hashed URLs and would otherwise load without CSS or JavaScript.
RUN DJANGO_DEBUG=False \
    DJANGO_ALLOWED_HOSTS=localhost \
    DJANGO_SECRET_KEY=docker-build-only-not-used-at-runtime \
    DJANGO_CACHE_URL=redis://localhost:6379/0 \
    ALLOW_INSECURE_EMAIL_FOR_DEMO=True \
    python manage.py collectstatic --noinput

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import os, urllib.request; host=os.environ.get('DJANGO_ALLOWED_HOSTS','localhost').split(',')[0].strip() or 'localhost'; request=urllib.request.Request('http://127.0.0.1:'+os.environ.get('PORT','8000')+'/health/', headers={'Host':host,'X-Forwarded-Proto':'https'}); urllib.request.urlopen(request, timeout=4)" || exit 1

CMD ["sh", "-c", "python manage.py migrate --noinput && exec gunicorn musea.wsgi:application --bind 0.0.0.0:${PORT:-8000} --workers ${WEB_CONCURRENCY:-2} --threads ${GUNICORN_THREADS:-4} --timeout ${GUNICORN_TIMEOUT:-60} --access-logfile - --error-logfile -"]
