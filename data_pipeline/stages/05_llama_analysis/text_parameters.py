#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Stage 05: LLM scores for lyrics — lyrical_intensity and lyrical_mood (0–1), numeric columns only.

Reads embeded_data.csv; uses its `lyrics` column when present (normal 04_clustering output).
If `lyrics` is missing, loads lyrics from preproccessed.csv by `id`. Then calls Ollama.

Run:
  python text_parameters.py
  python text_parameters.py --dry-run --limit 10
  python text_parameters.py --output storage/embeded_data_scored.csv

Env: OLLAMA_GENERATE_URL, LLM_MODEL, STORAGE_DIR
"""

from __future__ import annotations

import argparse
import math
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import requests
from tqdm import tqdm

_STAGE05_DIR = Path(__file__).resolve().parent
if str(_STAGE05_DIR) not in sys.path:
    sys.path.insert(0, str(_STAGE05_DIR))

from common_analysis import (
    DEFAULT_EMBEDED_CSV,
    DEFAULT_PREPROCESSED_CSV,
    LLM_MODEL,
    OLLAMA_GENERATE_URL,
    parse_llm_json,
    sample_lyrics_lines_by_fraction,
)

SCORING_PROMPT = """You are scoring song LYRICS only (words), not the music.

Return a single JSON object with exactly these keys (numbers only, no other keys):
- "lyrical_intensity": number from 0.0 to 1.0 — how aggressive, confrontational, or heated the WORDS are (profanity, rage, calls to fight, rebellion = high; calm storytelling, meditation, mellow tone = low). Step for this value is 0.001.
- "lyrical_mood": number from 0.0 to 1.0 — how positive or uplifting the WORDS are (love, joy, hope = high; death, breakup, pain, hate = low). Step for this value is 0.001.

If lyrics are empty or not real lyrics, use 0.5 for both numbers.
(You may see an excerpt of the lyrics — score what is shown.)

Lyrics:
---
{lyrics}
---
JSON only, no markdown."""


def clip01(x: Any) -> float:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return 0.5
    if math.isnan(v):
        return 0.5
    return float(max(0.0, min(1.0, v)))


def score_lyrics_with_ollama(
    lyrics: str,
    *,
    model: str,
    max_lyrics_chars: int,
    lyrics_line_fraction: float,
    timeout: float,
) -> tuple[float, float]:
    body = (lyrics or "").strip()
    if not body:
        return 0.5, 0.5

    body = sample_lyrics_lines_by_fraction(body, lyrics_line_fraction)
    truncated = body[:max_lyrics_chars]
    prompt = SCORING_PROMPT.format(lyrics=truncated)
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "format": "json",
    }
    try:
        resp = requests.post(OLLAMA_GENERATE_URL, json=payload, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        text = (data.get("response") or "").strip()
        parsed = parse_llm_json(text)
        li = clip01(parsed.get("lyrical_intensity", 0.5))
        lm = clip01(parsed.get("lyrical_mood", 0.5))
        return li, lm
    except Exception:
        return 0.5, 0.5


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fill lyrical_intensity / lyrical_mood via Ollama (lyrics-only JSON scores).",
    )
    parser.add_argument("--embeded", type=Path, default=DEFAULT_EMBEDED_CSV)
    parser.add_argument("--preprocessed", type=Path, default=DEFAULT_PREPROCESSED_CSV)
    parser.add_argument("--output", type=Path, default=None, help="Output CSV.")
    parser.add_argument("--limit", type=int, default=None, help="Process at most this many rows.")
    parser.add_argument("--sleep", type=float, default=0.0)
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--max-lyrics-chars",
        type=int,
        default=6000,
        help="Max characters of lyrics sent to the model per track (lower = faster prefill).",
    )
    parser.add_argument(
        "--lyrics-line-fraction",
        type=float,
        default=0.2,
        metavar="FRAC",
        help="Fraction of lyric lines to send (0–1], spread across the song; default 0.2 = ~20%%. Use 1.0 for full text.",
    )
    args = parser.parse_args()

    if not (0.0 < args.lyrics_line_fraction <= 1.0):
        print("--lyrics-line-fraction must be in (0, 1]", file=sys.stderr)
        sys.exit(2)

    ep = args.embeded.resolve()
    pp = args.preprocessed.resolve()
    out_path = (args.output or ep).resolve()

    if not ep.is_file():
        print(f"Missing CSV: {ep}", file=sys.stderr)
        sys.exit(1)

    df = pd.read_csv(ep, encoding="utf-8-sig", low_memory=False)
    df["id"] = df["id"].astype(str)

    if "lyrics" in df.columns:
        lyrics_list = df["lyrics"].fillna("").astype(str).tolist()
    else:
        print("embeded_data.csv has no `lyrics` column; using preproccessed.csv instead")
        if not pp.is_file():
            print("Missing preproccessed.csv", file=sys.stderr)
            sys.exit(1)
        pre = pd.read_csv(pp, encoding="utf-8-sig", low_memory=False)
        if "lyrics" not in pre.columns:
            print("Column 'lyrics' missing in preprocessed CSV.", file=sys.stderr)
            sys.exit(1)
        pre_lyrics = pre[["id", "lyrics"]].copy()
        pre_lyrics["id"] = pre_lyrics["id"].astype(str)
        pre_lyrics = pre_lyrics.drop_duplicates(subset="id", keep="first")
        merged = df.merge(pre_lyrics, on="id", how="left")
        lyrics_list = merged["lyrics"].fillna("").astype(str).tolist()

    n_total = len(df)
    # Align with stage 04: omit limit or limit <= 0 → all rows.
    lim = args.limit
    if lim is None or lim <= 0:
        n_proc = n_total
    else:
        n_proc = min(lim, n_total)

    if "lyrical_intensity" in df.columns:
        intensities = pd.to_numeric(df["lyrical_intensity"], errors="coerce").tolist()
    else:
        intensities = [np.nan] * n_total
    if "lyrical_mood" in df.columns:
        moods = pd.to_numeric(df["lyrical_mood"], errors="coerce").tolist()
    else:
        moods = [np.nan] * n_total

    for i in tqdm(range(n_proc), total=n_proc, desc="Ollama lyric scores"):
        ly = lyrics_list[i]
        if args.dry_run:
            intensities[i] = 0.5
            moods[i] = 0.5
        else:
            li, lm = score_lyrics_with_ollama(
                ly,
                model=LLM_MODEL,
                max_lyrics_chars=args.max_lyrics_chars,
                lyrics_line_fraction=args.lyrics_line_fraction,
                timeout=args.timeout,
            )
            intensities[i] = li
            moods[i] = lm
            if args.sleep > 0:
                time.sleep(args.sleep)

    df = df.copy()
    for col in ("lyrical_intensity_text", "lyrical_mood_text"):
        if col in df.columns:
            df = df.drop(columns=[col])
    df["lyrical_intensity"] = intensities
    df["lyrical_mood"] = moods

    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"Wrote {n_total} rows ({n_proc} scored) to {out_path}", flush=True)


if __name__ == "__main__":
    main()
