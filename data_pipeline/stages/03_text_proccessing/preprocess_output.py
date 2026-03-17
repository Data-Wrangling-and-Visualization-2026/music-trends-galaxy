#!/usr/bin/env python3
"""
Build storage/preproccessed.csv from storage/output.csv.

Renames lyric columns to the galaxy schema, strips LRC-style timestamps from lyrics,
and sets lyrics_path to empty (no file path).
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# Project root storage (matches Docker ./storage for frontend)
_PROJECT_ROOT = Path(__file__).resolve().parents[3]  # music-trends-galaxy/
_DEFAULT_STORAGE = _PROJECT_ROOT / "storage"
DEFAULT_INPUT = _DEFAULT_STORAGE / "output.csv"
DEFAULT_OUTPUT = _DEFAULT_STORAGE / "preproccessed.csv"

# Target column order (must match downstream / API expectations)
OUTPUT_COLUMNS = [
    "id",
    "name",
    "album",
    "album_id",
    "artists",
    "artist_ids",
    "track_number",
    "disc_number",
    "explicit",
    "danceability",
    "energy",
    "key",
    "loudness",
    "mode",
    "speechiness",
    "acousticness",
    "instrumentalness",
    "liveness",
    "valence",
    "tempo",
    "duration_ms",
    "time_signature",
    "year",
    "release_date",
    "lyrics",
    "lyrics_source",
    "lyrics_path",
]

# [mm:ss.xx], [m:ss], [mm:ss], optional fractional seconds with . or ,
_LRC_BRACKET = re.compile(
    r"\[(\d{1,2}:)?\d{1,2}[:.,]\d{2,3}\]\s*",
)
# <00:00.00> variants
_LRC_ANGLE = re.compile(
    r"<\d{1,2}:\d{2}(?:\.\d{2,3})?>\s*",
)
# Pure millisecond markers like [12345]
_LRC_MS = re.compile(r"\[\d{3,}\]\s*")


def strip_lyrics_timestamps(text: object) -> str:
    """Remove common synced-lyrics timestamp tokens; return plain line-oriented text."""
    if text is None or (isinstance(text, float) and np.isnan(text)):
        return ""
    s = str(text)
    if not s.strip():
        return ""
    s = _LRC_BRACKET.sub("", s)
    s = _LRC_ANGLE.sub("", s)
    s = _LRC_MS.sub("", s)
    return s.strip()


def transform_chunk(chunk: pd.DataFrame) -> pd.DataFrame:
    """Map one input chunk to OUTPUT_COLUMNS."""
    if "lyrics_text" in chunk.columns:
        raw_lyrics = chunk["lyrics_text"]
    elif "lyrics" in chunk.columns:
        raw_lyrics = chunk["lyrics"]
    else:
        raise KeyError(
            "Input must contain 'lyrics_text' or 'lyrics'. "
            f"Got: {list(chunk.columns)}"
        )

    out = pd.DataFrame(index=chunk.index)
    for col in OUTPUT_COLUMNS:
        if col == "lyrics":
            out[col] = raw_lyrics.map(strip_lyrics_timestamps)
        elif col == "lyrics_path":
            out[col] = np.nan
        elif col == "lyrics_source" and "lyrics_source" in chunk.columns:
            out[col] = chunk["lyrics_source"]
        elif col in chunk.columns:
            out[col] = chunk[col]
        else:
            out[col] = np.nan

    return out[OUTPUT_COLUMNS]


def main(
    input_csv: Path,
    output_csv: Path,
    chunksize: int,
) -> None:
    input_csv = input_csv.resolve()
    output_csv = output_csv.resolve()

    if not input_csv.is_file():
        print(f"Input not found: {input_csv}", file=sys.stderr)
        sys.exit(1)

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    first = True
    total_rows = 0

    reader = pd.read_csv(input_csv, chunksize=chunksize)
    for chunk in reader:
        block = transform_chunk(chunk)
        block.to_csv(
            output_csv,
            mode="w" if first else "a",
            header=first,
            index=False,
        )
        first = False
        total_rows += len(block)

    print(f"Wrote {total_rows} rows to {output_csv}")


if __name__ == "__main__":
    p = argparse.ArgumentParser(
        description="Convert output.csv to preproccessed.csv (clean lyrics, fixed columns).",
    )
    p.add_argument(
        "input",
        nargs="?",
        type=Path,
        default=DEFAULT_INPUT,
        help=f"Source CSV (default: {DEFAULT_INPUT})",
    )
    p.add_argument(
        "output",
        nargs="?",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Destination CSV (default: {DEFAULT_OUTPUT})",
    )
    p.add_argument(
        "--chunksize",
        type=int,
        default=10_000,
        help="Rows per read chunk (memory vs. speed).",
    )
    args = p.parse_args()
    main(args.input, args.output, args.chunksize)
