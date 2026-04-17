#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Stage 05: min / max / mean metrics per album_id (no LLM).

Reads embeded_data.csv, groups by album_id.

Output: storage/album_descriptions.json (metrics only; no description field).

Env: STORAGE_DIR
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd

_STAGE05_DIR = Path(__file__).resolve().parent
if str(_STAGE05_DIR) not in sys.path:
    sys.path.insert(0, str(_STAGE05_DIR))

from common_analysis import (
    DEFAULT_EMBEDED_CSV,
    STORAGE_DIR,
    aggregate_metric_stats,
)

DEFAULT_OUTPUT_JSON: Path = STORAGE_DIR / "album_descriptions.json"


def main() -> None:
    parser = argparse.ArgumentParser(description="Aggregate track metrics per album (no LLM).")
    parser.add_argument("--embeded", type=Path, default=DEFAULT_EMBEDED_CSV)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--min-tracks", type=int, default=1, help="Skip albums with fewer tracks.")
    parser.add_argument("--limit", type=int, default=None, help="Process only first N albums (sorted by album_id).")
    args = parser.parse_args()

    ep = args.embeded.resolve()
    if not ep.is_file():
        print(f"Missing CSV: {ep}", file=sys.stderr)
        sys.exit(1)

    df = pd.read_csv(ep, encoding="utf-8-sig", low_memory=False)
    if "album_id" not in df.columns:
        print("Column album_id not found in embeded_data.csv", file=sys.stderr)
        sys.exit(1)

    df["_aid"] = df["album_id"].astype(str).str.strip()
    df = df[df["_aid"].ne("") & df["_aid"].ne("nan")]

    codes = sorted(df["_aid"].unique())
    if args.limit is not None and args.limit > 0:
        codes = codes[: args.limit]

    out: dict[str, Any] = {
        "entity": "album",
        "source": "aggregate_metrics",
        "input_embeded_csv": str(ep),
        "albums": {},
    }

    for album_id in codes:
        sub = df[df["_aid"] == album_id]
        n = len(sub)
        if n < args.min_tracks:
            continue
        metric_stats = aggregate_metric_stats(sub)
        title = str(sub.iloc[0].get("album", "") or "").strip() or album_id
        out["albums"][album_id] = {
            "id": album_id,
            "album_title": title[:300],
            "track_count": n,
            "metrics": metric_stats,
        }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"Wrote {len(out['albums'])} albums to {args.output}", flush=True)


if __name__ == "__main__":
    main()
