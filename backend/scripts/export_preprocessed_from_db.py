"""
Export preprocessed_tracks -> CSV using the same column order as stage 03 (OUTPUT_COLUMNS).

Use this CSV as input for offline embedding/clustering steps outside the app.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import pandas as pd
from sqlalchemy.orm import Session

BACKEND_DIR = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BACKEND_DIR.parent
sys.path.insert(0, str(BACKEND_DIR))
sys.path.insert(0, str(SCRIPTS_DIR))

_preprocess_dir = PROJECT_ROOT / "data_pipeline" / "stages" / "03_text_proccessing"
sys.path.insert(0, str(_preprocess_dir))
from preprocess_output import OUTPUT_COLUMNS

from app.database import SessionLocal
from app.models import PreprocessedTrack


def export_preprocessed_csv(session: Session, csv_path: Path) -> int:
    """
    Write all preprocessed_tracks rows using OUTPUT_COLUMNS order.
    """
    tracks = session.query(PreprocessedTrack).order_by(PreprocessedTrack.id).all()
    rows = []
    for t in tracks:
        rows.append(
            {
                "id": t.id,
                "name": t.name,
                "album": t.album,
                "album_id": t.album_id,
                "artists": t.artists,
                "artist_ids": t.artist_ids,
                "track_number": t.track_number,
                "disc_number": t.disc_number,
                "explicit": t.explicit,
                "danceability": t.danceability,
                "energy": t.energy,
                "key": t.key,
                "loudness": t.loudness,
                "mode": t.mode,
                "speechiness": t.speechiness,
                "acousticness": t.acousticness,
                "instrumentalness": t.instrumentalness,
                "liveness": t.liveness,
                "valence": t.valence,
                "tempo": t.tempo,
                "duration_ms": t.duration_ms,
                "time_signature": t.time_signature,
                "year": t.year,
                "release_date": t.release_date,
                "lyrics": t.lyrics,
                "lyrics_source": t.lyrics_source,
                "lyrics_path": t.lyrics_path,
            }
        )
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(rows, columns=OUTPUT_COLUMNS)
    df.to_csv(csv_path, index=False)
    return len(df)


def main() -> None:
    parser = argparse.ArgumentParser(description="Export preprocessed_tracks to CSV.")
    parser.add_argument("--output", "-o", type=Path, default=None, help="Output CSV path.")
    parser.add_argument("--storage", type=Path, default=None, help="Storage directory.")
    args = parser.parse_args()

    storage = (args.storage or Path(os.getenv("STORAGE_DIR", str(PROJECT_ROOT / "storage")))).resolve()
    out = args.output or (storage / "preproccessed.csv")

    session: Session = SessionLocal()
    try:
        n = export_preprocessed_csv(session, out.resolve())
        print(f"[export] wrote {n} rows to {out}", flush=True)
    finally:
        session.close()


if __name__ == "__main__":
    main()
