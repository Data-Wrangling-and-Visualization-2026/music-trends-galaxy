#!/bin/sh
set -e

echo "Ensuring DB tables..."
python /app/scripts/init_db.py

echo "Generate static demo assets (manifest, chunks, covers)..."
python /app/scripts/generate_fake_data.py

echo "Starting FastAPI server..."
exec "$@"
