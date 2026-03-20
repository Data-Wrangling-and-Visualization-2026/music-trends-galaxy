"""
Serve scatter-plot points and track list from SQLite (galaxy_tracks table only).
No CSV fallback. Fails with error if DB is empty or unavailable.
"""

from __future__ import annotations

import random
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import GalaxyTrack
from app.schemas import (
    GalaxyPoint,
    GalaxyPointsResponse,
    GalaxyTrackListItem,
    GalaxyTracksResponse,
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


router = APIRouter(prefix="/api/galaxy", tags=["Galaxy"])

_NO_DB_MSG = (
    "Galaxy data not available. Run pipeline (03→04), ensure storage/embeded_data.csv exists, "
    "then start Docker so seed_embeded_data.py populates galaxy_tracks."
)


def _ensure_galaxy_data(db: Session) -> None:
    """Raise HTTPException if galaxy_tracks is empty or missing."""
    try:
        total = db.query(GalaxyTrack).count()
    except OperationalError as e:
        raise HTTPException(
            status_code=503,
            detail=f"Database error (galaxy_tracks table missing?): {e}",
        )
    if total == 0:
        raise HTTPException(
            status_code=503,
            detail=_NO_DB_MSG,
        )


@router.get("/points", response_model=GalaxyPointsResponse)
def get_galaxy_points(
    limit: int = Query(8_000, ge=1, le=120_000),
    seed: int = Query(42, description="RNG seed for random sample mode"),
    sample: str = Query(
        "first",
        description="'first' or 'random'",
    ),
    db: Session = Depends(get_db),
):
    _ensure_galaxy_data(db)

    total = db.query(GalaxyTrack).count()
    if sample == "random" and total > limit:
        random.seed(seed)
        ids = [row[0] for row in db.query(GalaxyTrack.id).all()]
        selected = random.sample(ids, min(limit, len(ids)))
        rows = db.query(GalaxyTrack).filter(GalaxyTrack.id.in_(selected)).all()
    else:
        rows = db.query(GalaxyTrack).order_by(GalaxyTrack.id).limit(limit).all()

    points = [
        GalaxyPoint(
            id=r.id,
            name=r.name or "",
            album=r.album,
            artists=r.artists,
            x=r.x_coord,
            y=r.y_coord,
            lyrical_intensity=float(r.lyrical_intensity) if r.lyrical_intensity is not None else 0.5,
            lyrical_mood=float(r.lyrical_mood) if r.lyrical_mood is not None else 0.5,
            energy=float(r.energy) if r.energy is not None else 0.5,
            valence=float(r.valence) if r.valence is not None else 0.5,
        )
        for r in rows
    ]
    return GalaxyPointsResponse(
        points=points,
        count=len(points),
        source_csv="sqlite",
        sample_mode=sample,
    )


@router.get("/tracks", response_model=GalaxyTracksResponse)
def list_galaxy_tracks(
    limit: int = Query(5_000, ge=1, le=50_000),
    db: Session = Depends(get_db),
):
    _ensure_galaxy_data(db)

    rows = db.query(GalaxyTrack).order_by(GalaxyTrack.id).limit(limit).all()
    tracks = [
        GalaxyTrackListItem(
            id=r.id,
            name=r.name or "",
            album=r.album,
            artists=r.artists,
            x=r.x_coord,
            y=r.y_coord,
        )
        for r in rows
    ]
    return GalaxyTracksResponse(
        tracks=tracks,
        count=len(tracks),
        source_csv="sqlite",
    )
