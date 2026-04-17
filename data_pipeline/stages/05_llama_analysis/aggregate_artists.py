#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Stage 05: min / max / mean metrics per Spotify artist (no LLM).

Joins embeded_data with preproccessed, groups tracks by artist_ids.

Output: storage/artist_descriptions.json (metrics only; no description field).

Env: STORAGE_DIR
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

_STAGE05_DIR = Path(__file__).resolve().parent
if str(_STAGE05_DIR) not in sys.path:
    sys.path.insert(0, str(_STAGE05_DIR))

from common_analysis import (
    DEFAULT_EMBEDED_CSV,
    DEFAULT_PREPROCESSED_CSV,
    STORAGE_DIR,
    aggregate_metric_stats,
    load_merged_embeded_preprocessed,
    parse_artist_ids,
)

DEFAULT_OUTPUT_JSON: Path = STORAGE_DIR / "artist_descriptions.json"


def main() -> None:
    parser = argparse.ArgumentParser(description="Aggregate track metrics per artist (no LLM).")
    parser.add_argument("--embeded", type=Path, default=DEFAULT_EMBEDED_CSV)
    parser.add_argument("--preprocessed", type=Path, default=DEFAULT_PREPROCESSED_CSV)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--min-tracks", type=int, default=1, help="Skip artists with fewer tracks.")
    parser.add_argument("--limit", type=int, default=None, help="Process only first N artists (sorted by id).")
    args = parser.parse_args()

    ep = args.embeded.resolve()
    pp = args.preprocessed.resolve()
    if not ep.is_file() or not pp.is_file():
        print(f"Missing CSV: {ep} or {pp}", file=sys.stderr)
        sys.exit(1)

    m = load_merged_embeded_preprocessed(ep, pp)
    if "artist_ids" not in m.columns:
        print("preproccessed merge must include artist_ids column", file=sys.stderr)
        sys.exit(1)

    artist_to_track_ids: dict[str, set[str]] = defaultdict(set)
    for _, row in m.iterrows():
        tid = str(row["id"])
        for aid in parse_artist_ids(row.get("artist_ids")):
            artist_to_track_ids[aid].add(tid)

    artist_ids_sorted = sorted(artist_to_track_ids.keys())
    if not artist_ids_sorted:
        print(
            "No artists: empty or unparseable artist_ids. "
            'Use JSON or Python list strings, e.g. ["spotifyArtistId"].',
            file=sys.stderr,
        )
    if args.limit is not None and args.limit > 0:
        artist_ids_sorted = artist_ids_sorted[: args.limit]

    out: dict[str, Any] = {
        "entity": "artist",
        "source": "aggregate_metrics",
        "input_embeded_csv": str(ep),
        "input_preprocessed_csv": str(pp),
        "artists": {},
    }

    for aid in artist_ids_sorted:
        tids = artist_to_track_ids[aid]
        if len(tids) < args.min_tracks:
            continue
        sub = m[m["id"].isin(tids)]
        n = len(sub)
        metric_stats = aggregate_metric_stats(sub)
        display_name: str = aid
        art = str(sub.iloc[0].get("artists", "") or "").strip()
        if art:
            display_name = art[:200]
        out["artists"][aid] = {
            "id": aid,
            "display_name": display_name,
            "track_count": n,
            "metrics": metric_stats,
        }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"Wrote {len(out['artists'])} artists to {args.output}", flush=True)


if __name__ == "__main__":
    main()
