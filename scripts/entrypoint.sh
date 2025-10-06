#!/bin/sh
set -e

# Parse Redis host and port from REDIS_URL
REDIS_HOST=$(echo $REDIS_URL | sed -E 's|redis://([^:/]+).*|\1|')
REDIS_PORT=$(echo $REDIS_URL | sed -E 's|redis://[^:]+:([0-9]+).*|\1|')

# Wait for Postgres
echo "Waiting for Postgres at $DB_HOST:$DB_PORT..."
until nc -z $DB_HOST $DB_PORT; do
  echo "Postgres not ready, sleeping 1s..."
  sleep 1
done

# Wait for Redis
echo "Waiting for Redis at $REDIS_HOST:$REDIS_PORT..."
until nc -z $REDIS_HOST $REDIS_PORT; do
  echo "Redis not ready, sleeping 1s..."
  sleep 1
done

# Run migrations and collect static
echo "Running database migrations..."
python manage.py migrate --noinput

echo "Collecting static files..."
python manage.py collectstatic --noinput

# Start Gunicorn
echo "Starting Gunicorn..."
exec gunicorn myproject.asgi:application \
     -k uvicorn.workers.UvicornWorker \
     --bind 0.0.0.0:8000
