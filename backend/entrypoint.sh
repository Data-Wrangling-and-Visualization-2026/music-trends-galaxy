#!/bin/sh
set -e

echo "Generating fake data..."
python /app/scripts/generate_fake_data.py

echo "Starting FastAPI server..."
exec "$@"