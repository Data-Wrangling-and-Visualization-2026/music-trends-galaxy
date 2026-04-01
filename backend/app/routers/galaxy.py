"""
Galaxy scatter + track list from PostgreSQL: fact_galaxy_points JOIN preprocessed_tracks.
Requires pipeline rebuild (or seed) so both tables are populated for the same track ids.
"""

from __future__ import annotations

import random

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.database import SessionLocal
from sqlalchemy.orm import aliased

from app.models import DimAlbum, DimArtist, DimCluster, FactGalaxyPoint, FactTrackAudioFeatures, PreprocessedTrack
from app.schemas import (
    ClusterLlmInfo,
    ClustersListResponse,
    DimAlbumBrief,
    DimArtistBrief,
    DimClusterRow,
    GalaxyPoint,
    GalaxyPointsResponse,
    GalaxyTrackListItem,
    GalaxyTracksResponse,
    MetricStatsBlock,
)


def _cluster_llm(row: DimCluster | None, code: str | None) -> ClusterLlmInfo | None:
    if not code or not str(code).strip():
        return None
    code = str(code).strip()
    if row is None:
        return ClusterLlmInfo(
            code=code,
            name=None,
            description=None,
            track_count=None,
            metrics=None,
            color=None,
        )
    metrics = None
    if row.metrics_json:
        try:
            metrics = MetricStatsBlock.model_validate(row.metrics_json)
        except Exception:
            metrics = None
    return ClusterLlmInfo(
        code=code,
        name=row.name,
        description=row.description,
        track_count=row.track_count,
        metrics=metrics,
        color=row.color,
    )


def _galaxy_rows_query(db: Session):
    DC = aliased(DimCluster)
    return (
        db.query(FactGalaxyPoint, PreprocessedTrack, DC)
        .join(PreprocessedTrack, FactGalaxyPoint.track_id == PreprocessedTrack.id)
        .outerjoin(DC, DC.code == FactGalaxyPoint.cluster_code)
    )


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


router = APIRouter(prefix="/api/galaxy", tags=["Galaxy"])

_NO_DB_MSG = (
    "Galaxy data not available. Load preprocessed_tracks and run backend/scripts/sync_db.py "
    "so fact_galaxy_points is populated."
)


def _galaxy_base_query(db: Session):
    """Rows that have both a preprocessed row and a galaxy embedding."""
    DC = aliased(DimCluster)
    return (
        db.query(FactGalaxyPoint, PreprocessedTrack, FactTrackAudioFeatures, DC)
        .join(PreprocessedTrack, FactGalaxyPoint.track_id == PreprocessedTrack.id)
        .outerjoin(FactTrackAudioFeatures, FactTrackAudioFeatures.track_id == PreprocessedTrack.id)
        .outerjoin(DC, DC.code == FactGalaxyPoint.cluster_code)
    )


def _fact_audio_dict(fa: FactTrackAudioFeatures | None) -> dict[str, float | int | None]:
    """Same field set as ``_pick_audio`` in api.py (fact_track_audio_features)."""
    return {
        "danceability": fa.danceability if fa is not None else None,
        "energy": fa.energy if fa is not None else None,
        "key": fa.key if fa is not None else None,
        "loudness": fa.loudness if fa is not None else None,
        "mode": fa.mode if fa is not None else None,
        "speechiness": fa.speechiness if fa is not None else None,
        "acousticness": fa.acousticness if fa is not None else None,
        "instrumentalness": fa.instrumentalness if fa is not None else None,
        "liveness": fa.liveness if fa is not None else None,
        "valence": fa.valence if fa is not None else None,
        "tempo": fa.tempo if fa is not None else None,
        "time_signature": fa.time_signature if fa is not None else None,
    }


def _ensure_galaxy_data(db: Session) -> None:
    try:
        total = db.query(FactGalaxyPoint).count()
    except OperationalError as e:
        raise HTTPException(
            status_code=503,
            detail=f"Database error (fact_galaxy_points missing?): {e}",
        )
    if total == 0:
        raise HTTPException(status_code=503, detail=_NO_DB_MSG)


def _score(v: float | None, default: float = 0.5) -> float:
    if v is None:
        return default
    return float(v)


def _genres_from_metrics(metrics: object) -> list[str]:
    if not metrics or not isinstance(metrics, dict):
        return []
    raw = metrics.get("genres")
    if not isinstance(raw, list):
        return []
    return [str(x).strip() for x in raw if str(x).strip()]


def _rows_after_sample(
    db: Session,
    base,
    limit: int,
    sample: str,
    seed: int,
):
    """Rows from a galaxy join query: first ``limit`` by id, or a random subset of that size."""
    total = base.count()
    if sample == "random" and total > limit:
        random.seed(seed)
        ids = [row[0] for row in db.query(FactGalaxyPoint.track_id).all()]
        if not ids:
            return []
        k = min(limit, len(ids))
        selected = set(random.sample(ids, k))
        return base.filter(FactGalaxyPoint.track_id.in_(selected)).all()
    return base.order_by(FactGalaxyPoint.track_id).limit(limit).all()


@router.get("/points", response_model=GalaxyPointsResponse)
def get_galaxy_points(
    limit: int = Query(5_000, ge=1, le=120_000),
    seed: int = Query(42, description="RNG seed for random sample mode"),
    sample: str = Query(
        "random",
        description="'first' or 'random'",
    ),
    db: Session = Depends(get_db),
):
    _ensure_galaxy_data(db)

    base = _galaxy_base_query(db)
    rows = _rows_after_sample(db, base, limit, sample, seed)

    points = [
        GalaxyPoint(
            id=g.track_id,
            name=p.name or "",
            album=p.album,
            artists=p.artists,
            x=float(g.x),
            y=float(g.y),
            z=float(g.z) if g.z is not None else 0.0,
            lyrical_intensity=_score(g.lyrical_intensity),
            lyrical_mood=_score(g.lyrical_mood),
            energy=_score(g.energy),
            valence=_score(g.valence),
            audio_features=_fact_audio_dict(fa),
            cluster_code=g.cluster_code,
            cluster=_cluster_llm(dc, g.cluster_code),
        )
        for g, p, fa, dc in rows
    ]
    return GalaxyPointsResponse(
        points=points,
        count=len(points),
        source_csv="fact_galaxy_points",
        sample_mode=sample,
    )


@router.get("/tracks", response_model=GalaxyTracksResponse)
def list_galaxy_tracks(
    limit: int = Query(5_000, ge=1, le=100_000),
    seed: int = Query(42, description="RNG seed for random sample mode"),
    sample: str = Query(
        "random",
        description="'first' or 'random'",
    ),
    db: Session = Depends(get_db),
):
    _ensure_galaxy_data(db)

    base = _galaxy_rows_query(db)
    rows = _rows_after_sample(db, base, limit, sample, seed)
    tracks = [
        GalaxyTrackListItem(
            id=g.track_id,
            name=p.name or "",
            album=p.album,
            album_id=p.album_id,
            artists=p.artists,
            artist_ids=p.artist_ids,
            year=p.year,
            x=float(g.x),
            y=float(g.y),
            z=float(g.z) if g.z is not None else 0.0,
            cluster_code=g.cluster_code,
            cluster=_cluster_llm(d_cl, g.cluster_code),
        )
        for g, p, d_cl in rows
    ]
    return GalaxyTracksResponse(
        tracks=tracks,
        count=len(tracks),
        source_csv="fact_galaxy_points",
        sample_mode=sample,
    )


@router.get("/artists", response_model=list[DimArtistBrief])
def list_dim_artists_for_filters(db: Session = Depends(get_db)):
    """All ``dim_artists`` rows for map filter pickers (id + name)."""
    try:
        rows = db.query(DimArtist).order_by(DimArtist.name.asc()).all()
    except OperationalError:
        return []
    return [
        DimArtistBrief(
            id=r.id,
            name=r.name or r.id,
            track_count=r.track_count,
            color=r.color,
            cover_image_id=r.cover_image_id,
            metrics_json=r.metrics_json if isinstance(r.metrics_json, dict) else None,
            genres=_genres_from_metrics(r.metrics_json),
        )
        for r in rows
    ]


@router.get("/albums", response_model=list[DimAlbumBrief])
def list_dim_albums_for_filters(db: Session = Depends(get_db)):
    """All ``dim_albums`` rows for map filter pickers (id + title)."""
    try:
        rows = db.query(DimAlbum).order_by(DimAlbum.title.asc()).all()
    except OperationalError:
        return []
    return [
        DimAlbumBrief(
            id=r.id,
            title=r.title or r.id,
            track_count=r.track_count,
            color=r.color,
            cover_image_id=r.cover_image_id,
            metrics_json=r.metrics_json if isinstance(r.metrics_json, dict) else None,
            genres=_genres_from_metrics(r.metrics_json),
        )
        for r in rows
    ]


@router.get("/clusters", response_model=ClustersListResponse)
def list_dim_clusters(db: Session = Depends(get_db)):
    """
    All rows from ``dim_clusters`` (codes, names, ``color``, ``metrics_json``).
    Used by the map for filters and cluster-tinted point colors. Empty table → ``clusters: []``.
    """
    try:
        rows = (
            db.query(DimCluster)
            .order_by(DimCluster.code.asc())
            .all()
        )
    except OperationalError:
        return ClustersListResponse(clusters=[], count=0)
    items = [DimClusterRow.model_validate(r) for r in rows]
    return ClustersListResponse(clusters=items, count=len(items))
