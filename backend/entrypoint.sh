#!/bin/sh
set -e

echo "Seeding galaxy tracks from embeded_data.csv..."
python /app/scripts/seed_embeded_data.py

echo "Generating fake data (songs, covers, manifest)..."
python /app/scripts/generate_fake_data.py

echo "Starting FastAPI server..."
exec "$@"