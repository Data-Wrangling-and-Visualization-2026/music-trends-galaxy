# Music Trends Galaxy

Music Trends Galaxy is a full-stack project for exploring music data as an interactive galaxy map.
The platform combines a Python data pipeline, a backend API, and a React frontend to transform track metadata into clusters and visual insights.

## Project structure

- `data_pipeline/` - stage-based ETL and analytics pipeline for preparing clustering/visualization data
- `backend/` - API and data access layer used by the application
- `frontend/` - user interface for map, filters, cluster exploration, and track details

## Quick start

From the repository root:

```bash
docker compose up --build
```

After startup, open the frontend in your browser and explore the generated music galaxy dataset.
