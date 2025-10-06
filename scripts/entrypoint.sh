#!/bin/sh
set -e

# Wait for Postgres
echo "Waiting for Postgres at $DB_HOST:$DB_PORT..."
until nc -z $DB_HOST $DB_PORT; do
  sleep 1
done

# Run migrations and collect static
echo "Running database migrations..."
python manage.py migrate --noinput

echo "Collecting static files..."
python manage.py collectstatic --noinput

# Start Gunicorn (exec CMD from Dockerfile)
exec "$@"
