
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, List, Sequence

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.config import COVERS_DIR, COVER_STORAGE_FILES_DIR
from app.database import SessionLocal
from app.models import (
    BridgeTrackArtist,
    DimAlbum,
    DimArtist,
    DimCluster,
    FactGalaxyPoint,
    FactTrackAudioFeatures,
    PreprocessedTrack,
    Song,
)
from app.schemas import (
    AlbumLlmInfo,
    ArtistLlmInfo,
    ClusterLlmInfo,
    MetricStatsBlock,
    SongInfo,
    SongListItem,
)
from app.utils.file_handlers import read_image_file

_BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(_BACKEND_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT / "scripts"))
from generate_rgb import rgb_from_valence_energy

router = APIRouter(prefix="/api", tags=["Runtime"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _metrics_block(raw: object) -> MetricStatsBlock | None:
    if not raw:
        return None
    try:
        return MetricStatsBlock.model_validate(raw)
    except Exception:
        return None

def _cluster_llm_full(db: Session, code: str | None) -> ClusterLlmInfo | None:
    if not code or not str(code).strip():
        return None
    code = str(code).strip()
    row = (
        db.query(DimCluster)
        .filter(DimCluster.code == code)
        .first()
    )
    if not row:
        return ClusterLlmInfo(code=code)
    return ClusterLlmInfo(
        code=code,
        name=row.name,
        description=row.description,
        track_count=row.track_count,
        metrics=_metrics_block(row.metrics_json),
        color=row.color,
    )


def _artist_llm_row(db: Session, artist_id: str) -> ArtistLlmInfo | None:
    a = db.query(DimArtist).filter(DimArtist.id == artist_id).first()
    if not a:
        return None
    return ArtistLlmInfo(
        id=a.id,
        name=a.name,
        track_count=a.track_count,
        metrics=_metrics_block(a.metrics_json),
        color=a.color,
        updated_at=a.updated_at,
        cover_image_id=a.cover_image_id,
    )


def _album_llm_row(db: Session, album_id: str | None) -> AlbumLlmInfo | None:
    if not album_id:
        return None
    a = db.query(DimAlbum).filter(DimAlbum.id == album_id).first()
    if not a:
        return None
    return AlbumLlmInfo(
        id=a.id,
        title=a.title,
        track_count=a.track_count,
        metrics=_metrics_block(a.metrics_json),
        color=a.color,
        updated_at=a.updated_at,
        cover_image_id=a.cover_image_id,
    )

def _parse_artists_list(artists_field: str | None) -> list[str]:
    if not artists_field:
        return []
    s = str(artists_field).strip()
    try:
        v: Any = json.loads(s)
        if isinstance(v, list):
            return [str(x).strip() for x in v if str(x).strip()]
    except Exception:
        # tolerate Python-like list strings: "['id1', 'id2']"
        t = s
        if t.startswith("[") and t.endswith("]"):
            t = t[1:-1]
        parts = [p.strip().strip("\"'") for p in re.split(r"\s*,\s*", t)]
        out = [p for p in parts if p and p.lower() != "none"]
        if out:
            return out
    return [p.strip().strip("\"'") for p in re.split(r"\s*,\s*", s) if p.strip()]


def _artist_names_from_bridge(db: Session, track_id: str) -> list[str] | None:
    rows: Sequence[tuple[BridgeTrackArtist, DimArtist]] = (
        db.query(BridgeTrackArtist, DimArtist)
        .join(DimArtist, DimArtist.id == BridgeTrackArtist.artist_id)
        .filter(BridgeTrackArtist.track_id == track_id)
        .order_by(BridgeTrackArtist.id)
        .all()
    )
    if not rows:
        return None
    return [a.name for _, a in rows]


def _display_artists(db: Session, p: PreprocessedTrack) -> list[str]:
    from_bridge = _artist_names_from_bridge(db, p.id)
    if from_bridge:
        return from_bridge
    return _parse_artists_list(p.artists)


def _artist_ids_for_track(db: Session, p: PreprocessedTrack) -> list[str]:
    from_bridge = (
        db.query(BridgeTrackArtist.artist_id)
        .filter(BridgeTrackArtist.track_id == p.id)
        .order_by(BridgeTrackArtist.id)
        .all()
    )
    if from_bridge:
        return [str(row[0]) for row in from_bridge if row and row[0]]
    return _parse_artists_list(p.artist_ids)


def _cluster_name(db: Session, code: str | None) -> str | None:
    if not code or not str(code).strip():
        return None
    code = str(code).strip()
    row = (
        db.query(DimCluster)
        .filter(DimCluster.code == code)
        .first()
    )
    return row.name if row else None


def _pick_audio(
    fa: FactTrackAudioFeatures | None,
) -> dict[str, float | int | None]:
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


@router.get("/cover/{id}.jpeg")
async def get_cover(id: str):
    cover_path = COVERS_DIR / f"{id}.jpeg"
    image_data = await read_image_file(cover_path)
    return Response(content=image_data, media_type="image/jpeg")


@router.get("/cover/storage/album/{album_id}.jpg")
async def get_album_cover_from_storage(album_id: str, db: Session = Depends(get_db)):
    """
    Resolve ``dim_albums.cover_image_id`` from Postgres, serve ``storage/images/images/{image_id}.jpg``.
    """
    row = db.query(DimAlbum).filter(DimAlbum.id == album_id).first()
    if row is None or row.cover_image_id is None or int(row.cover_image_id) <= 0:
        raise HTTPException(status_code=404, detail="No album cover")
    path = COVER_STORAGE_FILES_DIR / f"{int(row.cover_image_id)}.jpg"
    image_data = await read_image_file(path)
    return Response(content=image_data, media_type="image/jpeg")


@router.get("/cover/storage/artist/{artist_id}.jpg")
async def get_artist_cover_from_storage(artist_id: str, db: Session = Depends(get_db)):
    row = db.query(DimArtist).filter(DimArtist.id == artist_id).first()
    if row is None or row.cover_image_id is None or int(row.cover_image_id) <= 0:
        raise HTTPException(status_code=404, detail="No artist cover")
    path = COVER_STORAGE_FILES_DIR / f"{int(row.cover_image_id)}.jpg"
    image_data = await read_image_file(path)
    return Response(content=image_data, media_type="image/jpeg")


def _song_to_list_item(song: Song) -> SongListItem:
    return SongListItem(
        id=song.id,
        name=song.name,
        artists=json.loads(song.artists),
        album=song.album,
        album_id=song.album_id,
    )


@router.get("/songs", response_model=List[SongListItem])
def list_songs(db: Session = Depends(get_db)):
    rows = db.query(Song).order_by(Song.id).all()
    return [_song_to_list_item(s) for s in rows]


@router.get("/song/{id}", response_model=SongInfo)
def get_song_info(id: int, db: Session = Depends(get_db)):
    song = db.query(Song).filter(Song.id == id).first()
    if not song:
        raise HTTPException(status_code=404, detail="Song not found")
    artists = json.loads(song.artists)
    return SongInfo(
        id=song.id,
        name=song.name,
        artists=artists,
        album=song.album,
        album_id=song.album_id,
        lyrics=song.lyrics,
    )


def _load_track_bundle(
    db: Session, track_id: str
) -> tuple[PreprocessedTrack, FactGalaxyPoint | None, FactTrackAudioFeatures | None]:
    row = (
        db.query(PreprocessedTrack, FactGalaxyPoint, FactTrackAudioFeatures)
        .select_from(PreprocessedTrack)
        .outerjoin(FactGalaxyPoint, FactGalaxyPoint.track_id == PreprocessedTrack.id)
        .outerjoin(FactTrackAudioFeatures, FactTrackAudioFeatures.track_id == PreprocessedTrack.id)
        .filter(PreprocessedTrack.id == track_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Track not found")
    p, g, fa = row
    return p, g, fa


@router.get("/tracks/{track_id}")
def get_track_details_for_ui(track_id: str, db: Session = Depends(get_db)):
    p, g, fa = _load_track_bundle(db, track_id)
    artists = _display_artists(db, p)
    artist_ids = _artist_ids_for_track(db, p)
    audio = _pick_audio(fa)
    energy_v = g.energy if g is not None and g.energy is not None else audio["energy"]
    valence_v = g.valence if g is not None and g.valence is not None else audio["valence"]

    cluster_code = g.cluster_code if g else None
    cluster_llm = _cluster_llm_full(db, cluster_code)
    album_llm = _album_llm_row(db, p.album_id)
    artists_detail = [
        x.model_dump()
        for x in (
            _artist_llm_row(db, aid) for aid in artist_ids
        )
        if x is not None
    ]

    musical_features = {
        **audio,
        "energy": energy_v,
        "valence": valence_v,
        "lyrical_intensity": g.lyrical_intensity if g is not None else None,
        "lyrical_mood": g.lyrical_mood if g is not None else None,
        "cluster": cluster_llm.model_dump() if cluster_llm else None,
    }

    artist_line = ", ".join(artists) if artists else "Unknown Artist"
    color = (g.color if g is not None and g.color else None) or rgb_from_valence_energy(
        float(valence_v) if valence_v is not None else None,
        float(energy_v) if energy_v is not None else None,
    )

    return {
        "id": p.id,
        "name": p.name or "",
        "artist_name": artist_line,
        "album_title": p.album or "Single",
        "album_id": p.album_id,
        "year": p.year,
        "release_date": p.release_date,
        "duration_ms": p.duration_ms,
        "lyrics": p.lyrics or "",
        "lyrics_source": p.lyrics_source,
        "artists": artists,
        "artist_ids": artist_ids,
        "artists_detail": artists_detail,
        "album": album_llm.model_dump() if album_llm else None,
        "cluster": cluster_llm.model_dump() if cluster_llm else None,
        "musical_features": musical_features,
        "color": color,
        "galaxy": None
        if g is None
        else {
            "x": g.x,
            "y": g.y,
            "z": g.z,
            "cluster_code": cluster_code,
            "cluster_name": _cluster_name(db, cluster_code),
        },
    }


@router.get("/song/{id}/details")
def get_song_details_flat(id: str, db: Session = Depends(get_db)):
    row = (
        db.query(PreprocessedTrack, FactGalaxyPoint, FactTrackAudioFeatures)
        .select_from(PreprocessedTrack)
        .join(FactGalaxyPoint, FactGalaxyPoint.track_id == PreprocessedTrack.id)
        .outerjoin(FactTrackAudioFeatures, FactTrackAudioFeatures.track_id == PreprocessedTrack.id)
        .filter(PreprocessedTrack.id == id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Track not found")

    p, g, fa = row
    artists = _display_artists(db, p)
    audio = _pick_audio(fa)

    return {
        "id": p.id,
        "name": p.name,
        "artists": artists,
        "album": p.album,
        "album_id": p.album_id,
        "year": p.year,
        "release_date": p.release_date,
        "lyrics": p.lyrics or "",
        "duration_ms": p.duration_ms,
        "x_coord": g.x,
        "y_coord": g.y,
        "z": g.z,
        "cluster_code": g.cluster_code,
        "cluster_name": _cluster_name(db, g.cluster_code),
        "lyrical_intensity": g.lyrical_intensity,
        "lyrical_mood": g.lyrical_mood,
        "energy": g.energy if g.energy is not None else audio["energy"],
        "valence": g.valence if g.valence is not None else audio["valence"],
        "audio_features": audio,
    }