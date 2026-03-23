#!/usr/bin/env python3
"""
Seed SQLite galaxy_tracks table from storage/embeded_data.csv.

Runs at container startup (entrypoint). Creates the table if missing and upserts rows.
"""

import csv
import os
import sqlite3
import sys
from pathlib import Path

# Paths: in Docker, storage is mounted at /app/storage; locally, project root has storage/
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
_default_csv = BASE_DIR / "storage" / "embeded_data.csv"
if not _default_csv.is_file():
    _default_csv = BASE_DIR.parent / "storage" / "embeded_data.csv"
CSV_PATH = Path(os.getenv("EMBEDED_DATA_CSV", str(_default_csv)))
DB_PATH = DATA_DIR / "database.sqlite"


def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not CSV_PATH.is_file():
        print(f"Warning: {CSV_PATH} not found. Skipping galaxy seed.", file=sys.stderr)
        return

    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS galaxy_tracks (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            album TEXT,
            album_id TEXT,
            artists TEXT,
            x_coord REAL NOT NULL,
            y_coord REAL NOT NULL,
            lyrical_intensity REAL,
            lyrical_mood REAL,
            energy REAL,
            valence REAL,
            lyrics TEXT
        )
    """)
    conn.commit()

    def safe_float(v, default=None):
        if v is None or v == "":
            return default
        try:
            return float(v)
        except (TypeError, ValueError):
            return default

    count = 0
    with CSV_PATH.open(newline="", encoding="utf-8-sig", errors="replace") as f:
        reader = csv.DictReader(f)
        for row in reader:
            track_id = str(row.get("id", "")).strip()
            if not track_id:
                continue
            x = safe_float(row.get("x_coord") or row.get("x"), 0.0)
            y = safe_float(row.get("y_coord") or row.get("y"), 0.0)
            cursor.execute(
                """
                INSERT OR REPLACE INTO galaxy_tracks
                (id, name, album, album_id, artists, x_coord, y_coord,
                 lyrical_intensity, lyrical_mood, energy, valence, lyrics)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    track_id,
                    str(row.get("name", "") or "")[:512],
                    str(row.get("album", "") or "")[:512] or None,
                    str(row.get("album_id", "") or "")[:128] or None,
                    str(row.get("artists", "") or "")[:2048] or None,
                    x,
                    y,
                    safe_float(row.get("lyrical_intensity")),
                    safe_float(row.get("lyrical_mood")),
                    safe_float(row.get("energy")),
                    safe_float(row.get("valence")),
                    str(row.get("lyrics", "") or "")[:50000] or None,
                ),
            )
            count += 1
            if count % 5000 == 0:
                conn.commit()
                print(f"  Seeded {count} tracks...", flush=True)
    conn.commit()
    conn.close()
    print(f"Seeded {count} galaxy tracks from {CSV_PATH.name}.")


if __name__ == "__main__":
    main()
