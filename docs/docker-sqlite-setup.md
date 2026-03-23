# Docker + SQLite: Running with data from embeded_data.csv

## Overview

On container startup, the backend:
1. Reads `storage/embeded_data.csv` and populates the `galaxy_tracks` table in SQLite
2. Generates test songs, covers, and manifest
3. Starts the API; the frontend receives data through the backend from SQLite

## Run

```bash
# 1. Ensure storage/embeded_data.csv exists (run pipeline 03→04)
ls storage/embeded_data.csv

# 2. Start services
docker compose up --build
```

- Frontend: http://localhost:3000  
- Map: http://localhost:3000/map  
- API: http://localhost:8000  

## Data flow

```
storage/embeded_data.csv   (mounted into container)
        ↓
entrypoint: seed_embeded_data.py
        ↓
backend/data/database.sqlite  (volume ./backend/data)
        ↓
FastAPI /api/galaxy/points, /api/galaxy/tracks
        ↓
Frontend
```

## Docker volumes

| Volume | Purpose |
|--------|---------|
| `./storage:/app/storage` | Read embeded_data.csv for seeding |
| `./backend/data:/app/data` | SQLite database.sqlite (read/write on startup) |

## Recreating the database

```bash
# Remove backend data and start fresh
rm -rf backend/data/database.sqlite
docker compose up --build
```

On the next startup, the seed will repopulate `galaxy_tracks` from the CSV.

**Important:** The backend reads only from SQLite. If the table is empty or missing, the API returns 503.
