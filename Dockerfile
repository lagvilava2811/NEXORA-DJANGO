FROM python:3.13-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN addgroup --system nexora && adduser --system --ingroup nexora nexora
WORKDIR /app

COPY requirements.txt ./
RUN python -m pip install --upgrade pip && python -m pip install -r requirements.txt

COPY . .
RUN DJANGO_DEBUG=True DJANGO_SECRET_KEY=build-only-placeholder python manage.py collectstatic --noinput && \
    chown -R nexora:nexora /app

USER nexora
EXPOSE 8000

CMD ["sh", "-c", "python manage.py migrate --noinput && gunicorn musea.wsgi:application --bind 0.0.0.0:${PORT:-8000} --workers 1 --threads 4 --timeout 60"]
