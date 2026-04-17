#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Stage 05 (Llama / Ollama): English blurbs + min/max/mean metrics per cluster.

Uses the ``cluster`` column in embeded_data.csv (stage 04 HDBSCAN labels). There is a single
cluster dimension — no separate "deep" / "wide" levels.

For each cluster code in that column:
  - metrics: min/max/mean over ALL tracks in that cluster (lyrical_intensity, lyrical_mood, energy, valence)
  - description_en: one Ollama call, with a random sample of tracks for lyric excerpts only

Joins rows with preproccessed.csv on ``id`` for lyrics excerpts.

Output: storage/cluster_descriptions.json (default; override with --output).

Run:
  python data_pipeline/stages/05_llama_analysis/describe_clusters.py

Env: OLLAMA_GENERATE_URL, LLM_MODEL, STORAGE_DIR
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
from pathlib import Path
from typing import Any, Optional

import pandas as pd

from common_analysis import (
    DEFAULT_EMBEDED_CSV,
    DEFAULT_PREPROCESSED_CSV,
    LLM_MODEL,
    STORAGE_DIR,
    aggregate_metric_stats,
    cluster_label_as_number,
    format_stats_for_prompt,
    is_noise_cluster_label,
    ollama_cluster_name_and_description,
    sample_lyrics_lines_by_fraction,
)

CLUSTER_COLUMN = "cluster"


def _cluster_sort_key(code: Any) -> tuple[int, int, str]:
    n = cluster_label_as_number(code)
    if n is not None:
        return (0, n, "")
    return (1, 0, str(code))


def build_cluster_prompt(
    *,
    cluster_code: str,
    n_tracks: int,
    metric_stats: dict[str, dict[str, Optional[float]]],
    samples: list[dict[str, str]],
) -> str:
    lines = []
    for s in samples:
        title = s.get("title", "?")
        artist = s.get("artist", "")
        excerpt = s.get("excerpt", "")
        lines.append(f"- {title} — {artist}\n  lyrics excerpt: {excerpt}")

    stats_block = format_stats_for_prompt(metric_stats)

    return f"""You describe clusters of music tracks on an embedding map (grouped by similarity).
        Cluster code: {cluster_code}
        Number of tracks in this cluster: {n_tracks}
        Aggregate statistics over ALL tracks in this cluster (min / max / mean):
        {stats_block}
        Sample tracks (title — short lyrics excerpt):
        {chr(10).join(lines)}
        Return a single JSON object with exactly these keys:
        - "name": exactly two words (English) as a short thematic title for THIS cluster (sound/lyrics vibe). No punctuation except hyphen inside a word.
        - "description": one concise English sentence (max ~35 words) on what characterizes THIS cluster (sound and lyrics). Do not enumerate tracks.
        If data is sparse, still give a cautious general title and description.
        JSON only, no markdown.
    """


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate cluster blurbs via Ollama.")
    parser.add_argument("--embeded", type=Path, default=DEFAULT_EMBEDED_CSV, help="Path to embeded_data.csv (stage-04 output).")
    parser.add_argument("--preprocessed", type=Path, default=DEFAULT_PREPROCESSED_CSV, help="Path to preproccessed.csv (stage-03 output).")
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output JSON path (default: STORAGE_DIR/cluster_descriptions.json).",
    )
    parser.add_argument("--sample-tracks", type=int, default=8, help="How many tracks to sample for lyric excerpts in the LLM prompt (not used for min/max/mean).")
    parser.add_argument(
        "--lyrics-line-fraction",
        type=float,
        default=0.2,
        metavar="FRAC",
        help="Fraction of lyric lines per sampled track (~0.2 = 20%%); 1.0 = full text before char cap.",
    )
    parser.add_argument(
        "--max-lyrics-chars",
        type=int,
        default=400,
        help="Max characters per track lyric excerpt in the prompt (after line sampling).",
    )
    parser.add_argument("--seed", type=int, default=42, help="RNG seed for sampling tracks.")
    parser.add_argument("--sleep", type=float, default=0.0, help="Seconds to sleep after each Ollama request.")
    parser.add_argument("--timeout", type=float, default=120.0, help="HTTP timeout per Ollama request (seconds).")
    parser.add_argument("--limit", type=int, default=None, help="Process only first N clusters (after sorting codes).")
    parser.add_argument("--dry-run", action="store_true", help="Skip Ollama; still write metrics and sample_ids.")
    args = parser.parse_args()

    if not (0.0 < args.lyrics_line_fraction <= 1.0):
        print("--lyrics-line-fraction must be in (0, 1]", file=sys.stderr)
        sys.exit(2)
    if args.max_lyrics_chars < 1:
        print("--max-lyrics-chars must be >= 1", file=sys.stderr)
        sys.exit(2)

    if args.output is None:
        args.output = STORAGE_DIR / "cluster_descriptions.json"

    embeded_path = args.embeded.resolve()
    pre_path = args.preprocessed.resolve()
    if not embeded_path.is_file():
        print(f"Missing embeded_data CSV: {embeded_path}", file=sys.stderr)
        sys.exit(1)
    if not pre_path.is_file():
        print(f"Missing preprocessed CSV: {pre_path}", file=sys.stderr)
        sys.exit(1)

    emb = pd.read_csv(embeded_path, encoding="utf-8-sig")
    pre = pd.read_csv(pre_path, encoding="utf-8-sig")

    cluster_col = CLUSTER_COLUMN
    if cluster_col not in emb.columns:
        print(f"Column '{cluster_col}' not in {embeded_path.name}", file=sys.stderr)
        sys.exit(1)
    if "id" not in emb.columns or "id" not in pre.columns:
        print("Expected 'id' column in both CSVs", file=sys.stderr)
        sys.exit(1)

    pre = pre.set_index(pre["id"].astype(str), drop=False)
    emb["id"] = emb["id"].astype(str)
    emb["_cc"] = emb[cluster_col].astype(str).str.strip()
    emb = emb[emb["_cc"].ne("") & emb["_cc"].ne("nan")]
    emb = emb[~emb["_cc"].map(is_noise_cluster_label)]

    rng = random.Random(args.seed)

    codes = sorted(
        {str(c).strip() for c in emb["_cc"].unique() if not is_noise_cluster_label(str(c).strip())},
        key=_cluster_sort_key,
    )
    if args.limit is not None:
        codes = codes[: args.limit]
    total_clusters = len(codes)

    out: dict[str, Any] = {
        "cluster_column": cluster_col,
        "model": LLM_MODEL,
        "input_embeded_csv": str(embeded_path),
        "input_preprocessed_csv": str(pre_path),
        "clusters": {},
    }

    for idx, code in enumerate(codes, start=1):
        code_str = str(code).strip()
        sub = emb[emb["_cc"] == code_str]
        ids = sub["id"].tolist()
        n = len(ids)
        if n == 0:
            print(f"[{idx}/{total_clusters}] {code_str}: skipped (0 tracks)", flush=True)
            continue

        num = cluster_label_as_number(code_str)
        metric_stats = aggregate_metric_stats(sub)

        pick = ids if len(ids) <= args.sample_tracks else rng.sample(ids, args.sample_tracks)

        samples: list[dict[str, str]] = []
        for tid in pick:
            if tid not in pre.index:
                samples.append(
                    {
                        "title": str(tid),
                        "artist": "",
                        "excerpt": "(no row in preproccessed)",
                    }
                )
                continue
            pr = pre.loc[tid]
            if isinstance(pr, pd.DataFrame):
                pr = pr.iloc[0]
            name = str(pr.get("name", "") or "")[:200]
            artists = str(pr.get("artists", "") or "")[:120]
            lyrics = str(pr.get("lyrics", "") or "")
            body = sample_lyrics_lines_by_fraction(lyrics, args.lyrics_line_fraction)
            excerpt = body.replace("\n", " ").strip()[: args.max_lyrics_chars]
            if not excerpt:
                excerpt = "(no lyrics)"
            samples.append({"title": name, "artist": artists, "excerpt": excerpt})

        if args.dry_run:
            out["clusters"][code_str] = {
                "cluster_code": code_str,
                **({"cluster_number": num} if num is not None else {}),
                "track_count": n,
                "sample_ids": pick,
                "metrics": metric_stats,
                "dry_run": True,
            }
            print(f"[{idx}/{total_clusters}] [dry-run] {code_str}: n={n}", flush=True)
            continue

        prompt = build_cluster_prompt(
            cluster_code=code_str,
            n_tracks=n,
            metric_stats=metric_stats,
            samples=samples,
        )
        name, desc = ollama_cluster_name_and_description(prompt=prompt, timeout=args.timeout)
        out["clusters"][code_str] = {
            "cluster_code": code_str,
            **({"cluster_number": num} if num is not None else {}),
            "name": name,
            "track_count": n,
            "description_en": desc,
            "metrics": metric_stats,
        }
        preview = desc[:120] if len(desc) > 120 else desc
        print(f"[{idx}/{total_clusters}] {code_str} «{name}»: {preview}...", flush=True)
        if args.sleep > 0:
            time.sleep(args.sleep)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    n_done = len(out["clusters"])
    print(
        f"Wrote {args.output} ({n_done}/{total_clusters} clusters)",
        flush=True,
    )


if __name__ == "__main__":
    main()