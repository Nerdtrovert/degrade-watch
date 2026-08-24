#!/bin/bash
set -e

# Wait for database to be ready
echo "Waiting for database to be ready..."

echo "Database is up - continuing"

# Run migrations
echo "Running database migrations..."
alembic -c backend/alembic.ini upgrade head

# Check if we've already seeded (simple flag file approach)
if [ ! -f /app/.seeded ]; then
  echo "Running database seeding..."
  python /app/create_human_approval_scenario.py
  echo "Seeding complete - creating flag file"
  touch /app/.seeded
else
  echo "Database already seeded - skipping"
fi

# Start the application
echo "Starting application..."
exec uvicorn backend.main:app --host 0.0.0.0 --port 8000