#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Stage 05 orchestrator: text_parameters → artist/album metric aggregates → cluster LLM.

1. text_parameters.py — lyrical_intensity / lyrical_mood (numeric only).
2. aggregate_artists.py, aggregate_albums.py — min/max/mean per artist and album (no LLM).
3. describe_clusters.py — one LLM pass per HDBSCAN cluster (``cluster`` column → cluster_descriptions.json).

Run:
  python main.py
  python main.py --dry-run --limit 20

Env: OLLAMA_GENERATE_URL, LLM_MODEL, STORAGE_DIR (same as individual scripts).
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Any, Sequence

from common_analysis import DEFAULT_EMBEDED_CSV, DEFAULT_PREPROCESSED_CSV, STORAGE_DIR

_DIR = Path(__file__).resolve().parent

def _shared_cli(ns: argparse.Namespace, embeded_path: Path) -> list[str]:
    return [
        "--embeded",
        str(embeded_path.resolve()),
        "--preprocessed",
        str(Path(ns.preprocessed).resolve()),
        "--sleep",
        str(ns.sleep),
        "--timeout",
        str(ns.timeout),
        *([] if not ns.dry_run else ["--dry-run"]),
    ]

def _run(cmd: Sequence[str]) -> int:
    printable = " ".join(cmd)
    print(f"[stage05] {printable}", flush=True)
    r = subprocess.run(list(cmd), cwd=str(_DIR))
    return r.returncode

def main(cxt: Any = None) -> None:
    p = argparse.ArgumentParser(
        description="Run text_parameters, aggregate artist/album metrics, then cluster descriptions.",
    )
    p.add_argument("--embeded", type=Path, default=DEFAULT_EMBEDED_CSV)
    p.add_argument("--preprocessed", type=Path, default=DEFAULT_PREPROCESSED_CSV)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--sleep", type=float, default=0.0)
    p.add_argument("--timeout", type=float, default=120.0)


    p.add_argument(
        "--limit",
        type=int,
        default=None,
        help="first N tracks, first N artists/albums, first N clusters (for a short run)"
    )
    p.add_argument("--max-lyrics-chars", type=int, default=4000, help="Forward to text_parameters.")
    p.add_argument(
        "--lyrics-line-fraction",
        type=float,
        default=0.2,
        metavar="FRAC",
        help="describe_clusters (and text_parameters if enabled): fraction of lyric lines per excerpt; 1.0 = full lines before --cluster-excerpt-chars cap.",
    )
    p.add_argument(
        "--cluster-excerpt-chars",
        type=int,
        default=400,
        help="describe_clusters: max characters per sampled track lyric excerpt (passed as --max-lyrics-chars to describe_clusters).",
    )
    p.add_argument("--embeded-output", type=Path, default=None, help="Forward to text_parameters as --output.")

    p.add_argument("--sample-tracks", type=int, default=8)
    p.add_argument("--seed", type=int, default=42)

    ns, _ = p.parse_known_args()
    row_limit = ns.limit
    if row_limit is None and cxt is not None:
        row_limit = getattr(cxt, "limit", None)

    py = sys.executable

    '''tp_cmd: list[str] = [
        py,
        str(_DIR / "text_parameters.py"),
        *_shared_cli(ns, Path(ns.embeded)),
        "--max-lyrics-chars",
        str(ns.max_lyrics_chars),
        "--lyrics-line-fraction",
        str(ns.lyrics_line_fraction),
    ]

    if row_limit is not None:
        tp_cmd.extend(["--limit", str(row_limit)])'''

    def _describe_limit_args() -> list[str]:
        """Omit flag if unlimited."""
        if row_limit is None or row_limit <= 0:
            return []
        return ["--limit", str(row_limit)]

    '''if ns.embeded_output is not None:
        tp_cmd.extend(["--output", str(ns.embeded_output.resolve())])

    code = _run(tp_cmd)
    if code != 0:
        sys.exit(code)'''

    scored_embeded = (
        Path(ns.embeded_output).resolve() if ns.embeded_output is not None else Path(ns.embeded).resolve()
    )
    shared = _shared_cli(ns, scored_embeded)

    '''artists_agg: list[str] = [
        py,
        str(_DIR / "aggregate_artists.py"),
        "--embeded",
        str(scored_embeded),
        "--preprocessed",
        str(Path(ns.preprocessed).resolve()),
    ]
    artists_agg.extend(_describe_limit_args())

    albums_agg: list[str] = [
        py,
        str(_DIR / "aggregate_albums.py"),
        "--embeded",
        str(scored_embeded),
    ]
    albums_agg.extend(_describe_limit_args())

    for name, cmd in (
        ("aggregate_artists", artists_agg),
        ("aggregate_albums", albums_agg),
    ):
        code = _run(cmd)
        if code != 0:
            print(f"[stage05] {name} failed with exit code {code}", file=sys.stderr)
            sys.exit(code)'''

    clusters_cmd: list[str] = [
        py,
        str(_DIR / "describe_clusters.py"),
        *shared,
        "--sample-tracks",
        str(ns.sample_tracks),
        "--lyrics-line-fraction",
        str(ns.lyrics_line_fraction),
        "--max-lyrics-chars",
        str(ns.cluster_excerpt_chars),
        "--seed",
        str(ns.seed),
        "--output",
        str((STORAGE_DIR / "cluster_descriptions.json").resolve()),
    ]
    clusters_cmd.extend(_describe_limit_args())

    code = _run(clusters_cmd)
    if code != 0:
        print(f"[stage05] describe_clusters failed with exit code {code}", file=sys.stderr)
        sys.exit(code)

    dedupe_cmd = [py, str(_DIR / "dedupe_cluster_names.py")]
    code = _run(dedupe_cmd)
    if code != 0:
        print(f"[stage05] dedupe_cluster_names failed with exit code {code}", file=sys.stderr)
        sys.exit(code)

    print("[stage05] All steps finished.", flush=True)

if __name__ == "__main__":

    main()

