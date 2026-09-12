#!/usr/bin/env bash
set -e

echo "==> Ожидание PostgreSQL ${POSTGRES_HOST:-db}:${POSTGRES_PORT:-5432}..."
until pg_isready -h "${POSTGRES_HOST:-db}" -p "${POSTGRES_PORT:-5432}" -U "${POSTGRES_USER:-honestmark}" >/dev/null 2>&1; do
  sleep 1
done
echo "==> PostgreSQL доступен."

echo "==> Применение миграций..."
python manage.py migrate --noinput

echo "==> Сбор статики..."
python manage.py collectstatic --noinput

if [ "${LOAD_DEMO_DATA:-0}" = "1" ]; then
  echo "==> Загрузка демо-данных..."
  python manage.py seed_demo || true
fi

if [ "${CREATE_SUPERUSER:-0}" = "1" ] && [ -n "${DJANGO_SUPERUSER_USERNAME:-}" ]; then
  echo "==> Создание суперпользователя..."
  python manage.py createsuperuser --noinput || true
fi

echo "==> Запуск: $*"
exec "$@"
