"""
Serve scatter-plot points from pipeline CSV without loading lyric columns into memory.
"""

from __future__ import annotations

import csv
import math
import random
from pathlib import Path
from typing import Any

import pandas as pd
from fastapi import APIRouter, HTTPException, Query

from app.config import GALAXY_CSV_PATH
from app.schemas import (
    GalaxyPoint,
    GalaxyPointsResponse,
    GalaxyTrackListItem,
    GalaxyTracksResponse,
)

router = APIRouter(prefix="/api/galaxy", tags=["Galaxy"])

# Loaded in addition to x/y (keeps wide lyric columns out of memory).
EXTRA_COLS = [
    "id",
    "name",
    "album",
    "artists",
    "lyrical_intensity",
    "lyrical_mood",
    "energy",
    "valence",
]


def _read_header(path: Path) -> list[str]:
    with path.open(newline="", encoding="utf-8-sig", errors="replace") as f:
        row = next(csv.reader(f))
    return row


def _resolve_columns(header: list[str]) -> tuple[str, str, list[str]]:
    """Map x/y column names and pick available optional fields."""
    lower = {h.lower(): h for h in header}
    x_key = None
    for cand in ("x_coord", "x"):
        if cand in lower:
            x_key = lower[cand]
            break
    y_key = None
    for cand in ("y_coord", "y"):
        if cand in lower:
            y_key = lower[cand]
            break
    if not x_key or not y_key:
        raise HTTPException(
            status_code=500,
            detail="CSV must contain x_coord/y_coord (or x/y) columns.",
        )
    use = [x_key, y_key]
    for c in EXTRA_COLS:
        if c in header and c not in use:
            use.append(c)
    return x_key, y_key, use


def _float_cell(v: Any, default: float = 0.5) -> float:
    try:
        x = float(v)
    except (TypeError, ValueError):
        return default
    if math.isnan(x):
        return default
    return x


def _normalize_row(row: dict[str, Any], x_key: str, y_key: str) -> GalaxyPoint:
    xi = _float_cell(row.get("lyrical_intensity"), 0.5)
    return GalaxyPoint(
        id=str(row.get("id", "")),
        name=str(row.get("name", "") or ""),
        album=str(row.get("album", "") or "") if row.get("album") is not None else None,
        artists=str(row.get("artists", "") or "") if row.get("artists") is not None else None,
        x=_float_cell(row.get(x_key)),
        y=_float_cell(row.get(y_key)),
        lyrical_intensity=xi,
        lyrical_mood=_float_cell(row.get("lyrical_mood"), 0.5),
        energy=_float_cell(row.get("energy"), 0.5),
        valence=_float_cell(row.get("valence"), 0.5),
    )


def _reservoir_sample_rows(
    path: Path,
    usecols: list[str],
    k: int,
    seed: int,
) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    reservoir: list[dict[str, Any]] = []
    n = 0
    dtype_hints: dict[str, type | str] = {"id": str}
    for chunk in pd.read_csv(
        path,
        usecols=usecols,
        chunksize=12_000,
        dtype=dtype_hints,
        encoding="utf-8-sig",
        encoding_errors="replace",
        on_bad_lines="skip",
    ):
        chunk = chunk.replace({pd.NA: None})
        records = chunk.to_dict("records")
        for row in records:
            n += 1
            if len(reservoir) < k:
                reservoir.append(row)
            else:
                j = rng.randint(1, n)
                if j <= k:
                    reservoir[j - 1] = row
    return reservoir


def _take_first_rows(
    path: Path,
    usecols: list[str],
    k: int,
) -> list[dict[str, Any]]:
    df = pd.read_csv(
        path,
        usecols=usecols,
        nrows=k,
        dtype={"id": str},
        encoding="utf-8-sig",
        encoding_errors="replace",
        on_bad_lines="skip",
    )
    df = df.replace({pd.NA: None})
    return df.to_dict("records")


@router.get("/points", response_model=GalaxyPointsResponse)
def get_galaxy_points(
    limit: int = Query(8_000, ge=1, le=120_000),
    seed: int = Query(42, description="RNG seed for random sample mode"),
    sample: str = Query(
        "first",
        description="'first' = first N rows (fast); 'random' = reservoir sample over full file",
    ),
):
    path = GALAXY_CSV_PATH
    if not path.is_file():
        raise HTTPException(
            status_code=404,
            detail=(
                f"Galaxy CSV not found: {path}. "
                "Mount pipeline storage (e.g. ./storage:/app/storage) or set GALAXY_CSV_PATH."
            ),
        )

    try:
        header = _read_header(path)
    except StopIteration:
        raise HTTPException(status_code=500, detail="CSV is empty.")

    x_key, y_key, usecols = _resolve_columns(header)

    try:
        if sample == "first":
            raw = _take_first_rows(path, usecols, limit)
        else:
            raw = _reservoir_sample_rows(path, usecols, limit, seed)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to read galaxy CSV: {type(e).__name__}: {e}",
        )

    points = [_normalize_row(r, x_key, y_key) for r in raw]
    return GalaxyPointsResponse(
        points=points,
        count=len(points),
        source_csv=str(path.resolve()),
        sample_mode=sample,
    )


def _track_list_usecols(header: list[str], x_key: str, y_key: str) -> list[str]:
    use = [x_key, y_key]
    for c in ("id", "name", "album", "artists"):
        if c in header and c not in use:
            use.append(c)
    return use


def _row_to_track_item(row: dict[str, Any], x_key: str, y_key: str) -> GalaxyTrackListItem:
    return GalaxyTrackListItem(
        id=str(row.get("id", "") or ""),
        name=str(row.get("name", "") or ""),
        album=str(row.get("album", "") or "") if row.get("album") is not None else None,
        artists=str(row.get("artists", "") or "") if row.get("artists") is not None else None,
        x=_float_cell(row.get(x_key)),
        y=_float_cell(row.get(y_key)),
    )


@router.get("/tracks", response_model=GalaxyTracksResponse)
def list_galaxy_tracks(
    limit: int = Query(
        5_000,
        ge=1,
        le=50_000,
        description="Max rows returned (from the start of the file).",
    ),
):
    """Lightweight track list from embeded_data.csv for the home page."""
    path = GALAXY_CSV_PATH
    if not path.is_file():
        raise HTTPException(
            status_code=404,
            detail=(
                f"Galaxy CSV not found: {path}. "
                "Mount pipeline storage (e.g. ./storage:/app/storage) or set GALAXY_CSV_PATH."
            ),
        )

    try:
        header = _read_header(path)
    except StopIteration:
        raise HTTPException(status_code=500, detail="CSV is empty.")

    x_key, y_key, _ = _resolve_columns(header)
    usecols = _track_list_usecols(header, x_key, y_key)

    try:
        raw = _take_first_rows(path, usecols, limit)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to read galaxy CSV: {type(e).__name__}: {e}",
        )

    tracks = [_row_to_track_item(r, x_key, y_key) for r in raw]
    return GalaxyTracksResponse(
        tracks=tracks,
        count=len(tracks),
        source_csv=str(path.resolve()),
    )
