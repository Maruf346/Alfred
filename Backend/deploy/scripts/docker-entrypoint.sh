#!/bin/sh
set -e

if [ "${WAIT_FOR_DATABASE:-true}" = "true" ] && [ -n "${DB_HOST:-}" ]; then
  echo "Waiting for database ${DB_HOST}:${DB_PORT:-5432}..."
  until nc -z "$DB_HOST" "${DB_PORT:-5432}"; do
    sleep 2
  done
fi

if [ "${RUN_COLLECTSTATIC:-false}" = "true" ]; then
  echo "Collecting static files..."
  python manage.py collectstatic --noinput
fi

if [ "${RUN_MIGRATIONS:-false}" = "true" ]; then
  echo "Running database migrations..."
  python manage.py migrate --noinput
fi

exec "$@"
