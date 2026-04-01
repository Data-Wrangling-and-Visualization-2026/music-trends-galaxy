"""
Full database sync from pipeline CSV/JSON under ``--storage``.

Order:
  1. Upsert ``preprocessed_tracks`` from preprocessed CSV (stage-03).
  2. Rebuild ``dim_albums`` / ``dim_artists``, ``bridge_track_artists``,
     ``fact_track_audio_features`` from ``preprocessed_tracks``.
  3. Replace ``dim_clusters``, ``fact_galaxy_points``, ``bridge_track_clusters`` from a **single**
     read of ``embeded_data.csv``. Per-track ``color``: ``color`` column if valid ``#RRGGBB``, else
     :func:`generate_rgb.track_color_from_cluster` (cluster base + deviation vs cluster means when
     ``cluster_descriptions.json`` was loaded). Falls back to :func:`generate_rgb.rgb_from_valence_energy``
     if the row has no cluster code.
  4. Merge stage-05 JSON: ``cluster_descriptions.json``, ``artist_descriptions.json``,
     ``album_descriptions.json`` (cluster/artist/album metrics, names, colors).
  5. Optional SQLite at ``<storage>/images/image.db`` (same schema as pipeline stage 02):
     ``albums(id, image_id)``, ``artists(id, image_id)`` → set ``dim_albums.cover_image_id`` /
     ``dim_artists.cover_image_id`` for rows whose string ``id`` matches.

Environment: ``DATABASE_URL`` (via app config), optional ``PREPROCESSED_CSV``, ``STORAGE_DIR``.

  python sync_db.py
  python sync_db.py --storage D:/project/storage --preprocessed D:/project/storage/preproccessed.csv
  python sync_db.py --covers-only
  python sync_db.py --covers-only --image-db /path/to/image.db
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BACKEND_DIR.parent
sys.path.insert(0, str(BACKEND_DIR))
sys.path.insert(0, str(SCRIPTS_DIR))

from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import (
    PreprocessedTrack,
    DimAlbum,
    DimArtist,
    BridgeTrackArtist,
    FactTrackAudioFeatures,
    DimCluster,
    FactGalaxyPoint,
    BridgeTrackCluster,
)

from generate_rgb import (
    rgb_for_cluster_metrics,
    rgb_from_valence_energy,
    track_color_from_cluster,
)



def _safe_int(v):
    try:
        return int(v) if v not in (None, "") else None
    except Exception:
        return None


def _safe_float_cell(v):
    try:
        return float(v) if v not in (None, "") else None
    except Exception:
        return None


def _safe_bool(v):
    if v is None or v == "":
        return None
    s = str(v).strip().lower()
    if s in ("1", "true", "yes", "y"):
        return True
    if s in ("0", "false", "no", "n"):
        return False
    return None


def upsert_preprocessed_from_csv(session: Session, csv_path: Path) -> int:
    """Row-wise upsert into ``preprocessed_tracks``."""
    count = 0
    with csv_path.open(newline="", encoding="utf-8-sig", errors="replace") as f:
        for row in csv.DictReader(f):
            tid = str(row.get("id", "")).strip()
            if not tid:
                continue

            values = dict(
                id=tid,
                name=row.get("name"),
                album=row.get("album"),
                album_id=row.get("album_id"),
                artists=row.get("artists"),
                artist_ids=row.get("artist_ids"),
                track_number=_safe_int(row.get("track_number")),
                disc_number=_safe_int(row.get("disc_number")),
                explicit=_safe_bool(row.get("explicit")),
                duration_ms=_safe_int(row.get("duration_ms")),
                year=_safe_int(row.get("year")),
                release_date=row.get("release_date"),
                danceability=_safe_float_cell(row.get("danceability")),
                energy=_safe_float_cell(row.get("energy")),
                key=_safe_int(row.get("key")),
                loudness=_safe_float_cell(row.get("loudness")),
                mode=_safe_int(row.get("mode")),
                speechiness=_safe_float_cell(row.get("speechiness")),
                acousticness=_safe_float_cell(row.get("acousticness")),
                instrumentalness=_safe_float_cell(row.get("instrumentalness")),
                liveness=_safe_float_cell(row.get("liveness")),
                valence=_safe_float_cell(row.get("valence")),
                tempo=_safe_float_cell(row.get("tempo")),
                time_signature=_safe_int(row.get("time_signature")),
                lyrics=row.get("lyrics"),
                lyrics_source=row.get("lyrics_source"),
                lyrics_path=row.get("lyrics_path"),
            )

            ins = insert(PreprocessedTrack).values(**values)
            stmt = ins.on_conflict_do_update(
                index_elements=[PreprocessedTrack.id],
                set_={k: getattr(ins.excluded, k) for k in values.keys() if k != "id"},
            )
            session.execute(stmt)
            count += 1
            if count % 5000 == 0:
                session.commit()
                print(f"[preprocessed] upserted {count}...", flush=True)

    session.commit()
    return count




def _parse_artist_ids(s: str | None) -> list[str]:
    if not s:
        return []
    s = s.strip()
    try:
        v = json.loads(s)
        if isinstance(v, list):
            return [str(x).strip() for x in v if str(x).strip()]
    except Exception:
        # tolerate Python-like list strings: "['id1', 'id2']"
        t = s
        if t.startswith("[") and t.endswith("]"):
            t = t[1:-1]
        parts = [p.strip().strip("\"'") for p in t.split(",")]
        out = [p for p in parts if p and p.lower() != "none"]
        if out:
            return out
    return []


def _parse_artist_names(artists_field: str | None) -> list[str]:
    if not artists_field:
        return []
    return [p.strip() for p in re.split(r"\s*,\s*", str(artists_field)) if p.strip()]


def _coord_float(v, default: float = 0.0) -> float:
    try:
        if v is None or v == "":
            return default
        return float(v)
    except Exception:
        return default


def _opt_float(v) -> float | None:
    """Nullable float from CSV (empty / nan -> None)."""
    if v is None:
        return None
    s = str(v).strip()
    if not s or s.lower() == "nan":
        return None
    try:
        return float(s)
    except ValueError:
        return None


_RE_HEX_COLOR = re.compile(r"^#[0-9A-Fa-f]{6}$")


def _load_cluster_metrics_map(storage_dir: Path) -> dict[str, dict | None]:
    """``cluster_code`` -> ``metrics`` dict from ``cluster_descriptions.json`` if present."""
    path = storage_dir / "cluster_descriptions.json"
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    out: dict[str, dict | None] = {}
    for code, payload in (data.get("clusters") or {}).items():
        code = str(code).strip()
        if not code or not isinstance(payload, dict):
            continue
        m = payload.get("metrics")
        out[code] = m if isinstance(m, dict) else None
    return out


def _galaxy_point_color(row: dict, cluster_metrics_by_code: dict[str, dict | None]) -> str:
    """CSV override, else track_color_from_cluster, else valence/energy only."""
    raw = row.get("color")
    if raw is not None:
        s = str(raw).strip()
        if _RE_HEX_COLOR.match(s):
            return s
    cl = _cluster_code_from_csv_row(row)
    if cl:
        return track_color_from_cluster(
            cl,
            _opt_float(row.get("valence")),
            _opt_float(row.get("energy")),
            cluster_metrics_by_code.get(cl),
        )
    return rgb_from_valence_energy(_opt_float(row.get("valence")), _opt_float(row.get("energy")))


def rebuild_dims_and_audio(session: Session) -> int:
    """Rebuild dimension + audio feature tables from ``preprocessed_tracks``."""
    session.execute(delete(BridgeTrackArtist))
    session.execute(delete(FactTrackAudioFeatures))
    session.execute(delete(DimArtist))
    session.execute(delete(DimAlbum))
    session.commit()

    tracks = session.query(PreprocessedTrack).order_by(PreprocessedTrack.id).all()
    albums: dict[str, str] = {}
    artists: dict[str, str] = {}

    for t in tracks:
        if t.album_id and t.album:
            albums[str(t.album_id)] = str(t.album)

        ids = _parse_artist_ids(t.artist_ids)
        names = _parse_artist_names(t.artists)
        for i, aid in enumerate(ids):
            if aid not in artists:
                artists[aid] = names[i] if i < len(names) else aid

    for aid, title in albums.items():
        row = session.get(DimAlbum, aid)
        if row is None:
            session.add(DimAlbum(id=aid, title=title))
        else:
            row.title = title

    for arid, nm in artists.items():
        row = session.get(DimArtist, arid)
        if row is None:
            session.add(DimArtist(id=arid, name=nm))
        else:
            row.name = nm

    session.commit()

    for t in tracks:
        for arid in _parse_artist_ids(t.artist_ids):
            session.add(BridgeTrackArtist(track_id=t.id, artist_id=arid))

        session.add(
            FactTrackAudioFeatures(
                track_id=t.id,
                danceability=t.danceability,
                energy=t.energy,
                key=t.key,
                loudness=t.loudness,
                mode=t.mode,
                speechiness=t.speechiness,
                acousticness=t.acousticness,
                instrumentalness=t.instrumentalness,
                liveness=t.liveness,
                valence=t.valence,
                tempo=t.tempo,
                time_signature=t.time_signature,
            )
        )

    session.commit()
    return len(tracks)


def apply_image_db_cover_ids(session: Session, image_db_path: Path) -> None:
    """
    Map pipeline SQLite ``albums`` / ``artists`` tables into ``cover_image_id`` on dim tables.
    Files on disk are expected at ``storage/images/images/{image_id}.jpg`` (see API
    ``/api/cover/storage/...``).
    """
    if not image_db_path.is_file():
        print(f"[covers] skip: image DB not found ({image_db_path})", flush=True)
        return

    uri = f"file:{image_db_path.resolve().as_posix()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    try:
        cur = conn.cursor()
        n_albums = 0
        n_artists = 0

        try:
            rows_albums = cur.execute("SELECT id, image_id FROM albums").fetchall()
        except sqlite3.OperationalError as e:
            print(f"[covers] sqlite albums table: {e}", flush=True)
            rows_albums = []

        for aid, iid in rows_albums:
            aid_s = str(aid).strip()
            row = session.query(DimAlbum).filter(DimAlbum.id == aid_s).one_or_none()
            if row is not None:
                row.cover_image_id = int(iid) if iid is not None else None
                n_albums += 1

        try:
            rows_artists = cur.execute("SELECT id, image_id FROM artists").fetchall()
        except sqlite3.OperationalError as e:
            print(f"[covers] sqlite artists table: {e}", flush=True)
            rows_artists = []

        for arid, iid in rows_artists:
            ar_s = str(arid).strip()
            row = session.query(DimArtist).filter(DimArtist.id == ar_s).one_or_none()
            if row is not None:
                row.cover_image_id = int(iid) if iid is not None else None
                n_artists += 1

        session.commit()
        print(
            f"[covers] image.db -> Postgres: dim_albums rows touched={n_albums}, "
            f"dim_artists touched={n_artists}",
            flush=True,
        )
    finally:
        conn.close()


def _cluster_code_from_csv_row(row: dict) -> str:
    """Single cluster dimension: ``cluster`` column only."""
    return str(row.get("cluster") or "").strip()


def _ensure_cluster(session: Session, code: str) -> int:
    code = str(code).strip()
    row = (
        session.query(DimCluster)
        .filter(DimCluster.code == code)
        .one_or_none()
    )
    if row:
        return int(row.id)
    c = DimCluster(code=code, name=code, description=None)
    session.add(c)
    session.flush()
    return int(c.id)


def import_galaxy_from_embeded(
    session: Session,
    embeded_csv: Path,
    cluster_metrics_by_code: dict[str, dict | None],
) -> int:
    """One pass over ``embeded_data.csv`` — full ``fact_galaxy_points`` row per track."""
    session.execute(delete(BridgeTrackCluster))
    session.execute(delete(FactGalaxyPoint))
    session.execute(delete(DimCluster))
    session.commit()

    count = 0
    with embeded_csv.open(newline="", encoding="utf-8-sig", errors="replace") as f:
        for row in csv.DictReader(f):
            tid = str(row.get("id", "")).strip()
            if not tid:
                continue
            if session.get(PreprocessedTrack, tid) is None:
                continue

            cl = _cluster_code_from_csv_row(row)
            cid = _ensure_cluster(session, cl) if cl else None

            session.add(
                FactGalaxyPoint(
                    track_id=tid,
                    x=float(_coord_float(row.get("x_coord") or row.get("x"), 0.0)),
                    y=float(_coord_float(row.get("y_coord") or row.get("y"), 0.0)),
                    z=float(_coord_float(row.get("z_coord") or row.get("z"), 0.0)),
                    lyrical_intensity=_opt_float(row.get("lyrical_intensity")),
                    lyrical_mood=_opt_float(row.get("lyrical_mood")),
                    energy=_opt_float(row.get("energy")),
                    valence=_opt_float(row.get("valence")),
                    cluster_code=cl or None,
                    color=_galaxy_point_color(row, cluster_metrics_by_code),
                )
            )
            if cid is not None:
                session.add(BridgeTrackCluster(track_id=tid, cluster_id=cid))

            count += 1
            if count % 2000 == 0:
                session.commit()
                print(f"[galaxy] imported {count}...", flush=True)

    session.commit()
    return count




def _metric_mean(metrics: dict | None, key: str) -> float | None:
    if not metrics or not isinstance(metrics, dict):
        return None
    block = metrics.get(key)
    if not isinstance(block, dict):
        return None
    m = block.get("mean")
    if m is None:
        return None
    try:
        return float(m)
    except (TypeError, ValueError):
        return None


def _color_from_aggregate_metrics(metrics: dict | None) -> str | None:
    if not metrics:
        return None
    v = _metric_mean(metrics, "valence")
    e = _metric_mean(metrics, "energy")
    if v is None and e is None:
        return None
    return rgb_from_valence_energy(v, e)


def _parse_cluster_file(path: Path, session: Session) -> int:
    data = json.loads(path.read_text(encoding="utf-8"))
    model = data.get("model")
    clusters = data.get("clusters") or {}

    n = 0
    for code, payload in clusters.items():
        code = str(code).strip()
        if not code or not isinstance(payload, dict):
            continue

        desc_raw = payload.get("description_en") or payload.get("description") or ""
        desc = str(desc_raw).strip() or None
        name_raw = payload.get("name") or ""
        llm_name = str(name_raw).strip() or None

        metrics = payload.get("metrics")
        tc = payload.get("track_count")

        row = (
            session.query(DimCluster)
            .filter(DimCluster.code == code)
            .one_or_none()
        )

        if row is None:
            default_name = llm_name or code
            row = DimCluster(code=code, name=default_name[:256])
            session.add(row)

        if llm_name:
            row.name = llm_name[:256]
        row.description = desc
        row.metrics_json = metrics
        row.track_count = int(tc) if tc is not None else row.track_count
        row.llm_model = str(model) if model else row.llm_model
        row.llm_updated_at = datetime.now(timezone.utc)
        mv = _metric_mean(metrics, "valence") if isinstance(metrics, dict) else None
        me = _metric_mean(metrics, "energy") if isinstance(metrics, dict) else None
        row.color = rgb_for_cluster_metrics(mv, me, code)

        n += 1

    session.commit()
    return n


def _parse_artists_file(path: Path, session: Session) -> int:
    data = json.loads(path.read_text(encoding="utf-8"))
    artists = data.get("artists") or {}

    n = 0
    now = datetime.now(timezone.utc)

    for aid, payload in artists.items():
        aid = str(aid).strip()
        if not aid or not isinstance(payload, dict):
            continue

        metrics = payload.get("metrics")
        tc = payload.get("track_count")
        name = (payload.get("display_name") or aid).strip()

        row = session.query(DimArtist).filter(DimArtist.id == aid).one_or_none()

        if row is None:
            row = DimArtist(id=aid, name=name or aid)
            session.add(row)
        elif name:
            row.name = name

        row.metrics_json = metrics
        row.track_count = int(tc) if tc is not None else row.track_count
        row.updated_at = now
        row.color = _color_from_aggregate_metrics(metrics if isinstance(metrics, dict) else None)

        n += 1

    session.commit()
    return n


def _parse_albums_file(path: Path, session: Session) -> int:
    data = json.loads(path.read_text(encoding="utf-8"))
    albums = data.get("albums") or {}

    n = 0
    now = datetime.now(timezone.utc)

    for album_id, payload in albums.items():
        album_id = str(album_id).strip()
        if not album_id or not isinstance(payload, dict):
            continue

        metrics = payload.get("metrics")
        tc = payload.get("track_count")
        title = (payload.get("album_title") or album_id).strip()

        row = session.query(DimAlbum).filter(DimAlbum.id == album_id).one_or_none()
        if row is None:
            row = DimAlbum(id=album_id, title=title or album_id)
            session.add(row)
        elif title:
            row.title = title

        row.metrics_json = metrics
        row.track_count = int(tc) if tc is not None else row.track_count
        row.updated_at = now
        row.color = _color_from_aggregate_metrics(metrics if isinstance(metrics, dict) else None)

        n += 1

    session.commit()
    return n


def _cluster_description_paths(storage_dir: Path) -> list[Path]:
    p = storage_dir / "cluster_descriptions.json"
    return [p] if p.is_file() else []


def apply_stage05_json(storage_dir: Path, session: Session) -> None:
    """Merge cluster / artist / album JSON from stage 05."""
    a = storage_dir / "artist_descriptions.json"
    b = storage_dir / "album_descriptions.json"

    for c in _cluster_description_paths(storage_dir):
        print("clusters", c.name, _parse_cluster_file(c, session))
    if a.is_file():
        print("artists", _parse_artists_file(a, session))
    if b.is_file():
        print("albums", _parse_albums_file(b, session))


def run_covers_only_sync(
    *,
    storage_dir: Path,
    image_db_path: Path | None = None,
) -> None:
    """Only ``image.db`` → ``dim_albums.cover_image_id`` / ``dim_artists.cover_image_id``."""
    session: Session = SessionLocal()
    try:
        img_db = image_db_path if image_db_path is not None else (storage_dir / "images" / "image.db")
        apply_image_db_cover_ids(session, img_db)
    finally:
        session.close()


def run_full_sync(
    *,
    storage_dir: Path,
    preprocessed_csv: Path,
    embeded_csv: Path,
    image_db_path: Path | None = None,
) -> None:
    if not preprocessed_csv.is_file():
        print(f"[error] Missing preprocessed CSV: {preprocessed_csv}", file=sys.stderr)
        sys.exit(1)
    if not embeded_csv.is_file():
        print(f"[error] Missing embeded_data CSV: {embeded_csv}", file=sys.stderr)
        sys.exit(1)

    session: Session = SessionLocal()
    try:
        n_pre = upsert_preprocessed_from_csv(session, preprocessed_csv)
        print(f"[preprocessed] upserted total: {n_pre}", flush=True)

        n_dim = rebuild_dims_and_audio(session)
        print(f"[dims] rebuilt for {n_dim} tracks", flush=True)

        cluster_metrics = _load_cluster_metrics_map(storage_dir)
        n_gal = import_galaxy_from_embeded(session, embeded_csv, cluster_metrics)
        print(f"[galaxy] imported {n_gal} points", flush=True)

        apply_stage05_json(storage_dir, session)

        img_db = image_db_path if image_db_path is not None else (storage_dir / "images" / "image.db")
        apply_image_db_cover_ids(session, img_db)
    finally:
        session.close()


def main() -> None:
    default_storage = Path(os.getenv("STORAGE_DIR", str(PROJECT_ROOT / "storage"))).resolve()
    default_pre = Path(
        os.getenv("PREPROCESSED_CSV", str(default_storage / "preproccessed.csv"))
    ).resolve()

    p = argparse.ArgumentParser(
        description="Full DB sync: preprocessed CSV, dims/audio, embeded_data (one pass), stage-05 JSON.",
    )
    p.add_argument(
        "--storage",
        type=Path,
        default=default_storage,
        help="Directory with cluster/artist/album JSON and embeded_data.csv",
    )
    p.add_argument(
        "--preprocessed",
        type=Path,
        default=default_pre,
        help="Path to preproccessed.csv (stage-03)",
    )
    p.add_argument(
        "--embeded",
        type=Path,
        default=None,
        help="Path to embeded_data.csv (default: <storage>/embeded_data.csv)",
    )
    p.add_argument(
        "--image-db",
        type=Path,
        default=None,
        help="SQLite with albums/artists image_id (default: <storage>/images/image.db)",
    )
    p.add_argument(
        "--covers-only",
        action="store_true",
        help="Only map image.db → dim_albums / dim_artists (no CSV, no galaxy, no stage-05 JSON).",
    )
    args = p.parse_args()

    storage = args.storage.resolve()
    image_db = args.image_db.resolve() if args.image_db is not None else None

    if args.covers_only:
        run_covers_only_sync(storage_dir=storage, image_db_path=image_db)
        return

    pre = args.preprocessed.resolve()
    emb = args.embeded.resolve() if args.embeded is not None else (storage / "embeded_data.csv")

    run_full_sync(storage_dir=storage, preprocessed_csv=pre, embeded_csv=emb, image_db_path=image_db)


if __name__ == "__main__":
    main()
