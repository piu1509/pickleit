#!/bin/sh
set -e

# Run migrations and collect static files on container startup
echo "Running database migrations..."
python manage.py migrate --noinput

echo "Collecting static files..."
python manage.py collectstatic --noinput

# Start the application
exec "$@"
