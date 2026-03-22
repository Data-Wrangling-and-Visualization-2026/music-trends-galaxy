#!/usr/bin/env python3
"""
Score lyrics with Ollama (lyrical_intensity, lyrical_mood) and set 2D coordinates:

  x_coord = (valence + lyrical_mood) / 2
  y_coord = (energy + lyrical_intensity) / 2

Default input is storage/preproccessed.csv (from preprocess_output.py).
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd
import requests
from tqdm import tqdm

_PIPELINE_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_STORAGE = _PIPELINE_ROOT / "storage"
DEFAULT_INPUT_CSV = _DEFAULT_STORAGE / "preproccessed.csv"
DEFAULT_OUTPUT_CSV = _DEFAULT_STORAGE / "embeded_data.csv"

OLLAMA_GENERATE_URL = os.getenv(
    "OLLAMA_GENERATE_URL",
    "http://localhost:11434/api/generate",
)
# Chat/completion model for scoring (not the embedding model)
LLM_MODEL = os.getenv("LLM_MODEL", "llama3.2")

SCORING_PROMPT = """You are scoring song LYRICS only (words), not the music.

Return a single JSON object with exactly these keys:
- "lyrical_intensity": number from 0.0 to 1.0 — how aggressive, confrontational, or heated the WORDS are (profanity, rage, calls to fight, rebellion = high; calm storytelling, meditation, mellow tone = low).
- "lyrical_mood": number from 0.0 to 1.0 — how positive or uplifting the WORDS are (love, joy, hope = high; death, breakup, pain, hate = low).
- "lyrical_intensity_text": one short sentence (any language) explaining the intensity score.
- "lyrical_mood_text": one short sentence (any language) explaining the mood score.

If lyrics are empty or not real lyrics, use 0.5 for both numbers and explain briefly.

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


def parse_llm_json(raw: str) -> dict[str, Any]:
    """Extract JSON object from model output (handles minor wrapping)."""
    raw = raw.strip()
    if not raw:
        return {}
    # Strip ```json fences if present
    fence = re.match(r"^```(?:json)?\s*(.*)\s*```$", raw, re.DOTALL | re.IGNORECASE)
    if fence:
        raw = fence.group(1).strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    start = raw.find("{")
    end = raw.rfind("}")
    if start >= 0 and end > start:
        try:
            return json.loads(raw[start : end + 1])
        except json.JSONDecodeError:
            pass
    return {}


def score_lyrics_with_ollama(
    lyrics: str,
    model: str,
    max_lyrics_chars: int,
    timeout: float,
) -> tuple[float, float, str, str]:
    """
    Ask Ollama for scores and short text rationales.
    Returns (lyrical_intensity, lyrical_mood, lyrical_intensity_text, lyrical_mood_text).
    """
    body = (lyrics or "").strip()
    if not body:
        return (
            0.5,
            0.5,
            "Empty lyrics.",
            "Empty lyrics.",
        )

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
        lit = str(parsed.get("lyrical_intensity_text") or "").strip() or "—"
        lmt = str(parsed.get("lyrical_mood_text") or "").strip() or "—"
        return li, lm, lit, lmt
    except Exception as e:
        return (
            0.5,
            0.5,
            f"LLM error: {type(e).__name__}",
            f"LLM error: {type(e).__name__}",
        )


def coordinates_from_features(
    valence: Any,
    energy: Any,
    lyrical_mood: float,
    lyrical_intensity: float,
) -> tuple[float, float]:
    v = clip01(valence)
    e = clip01(energy)
    x = (v + lyrical_mood) / 2.0
    y = (e + lyrical_intensity) / 2.0
    return x, y


def main(
    input_csv: Path,
    output_csv: Path,
    chunksize: int,
    limit: Optional[int],
    sleep_s: float,
    max_lyrics_chars: int,
    request_timeout: float,
) -> None:
    input_csv = input_csv.resolve()
    output_csv = output_csv.resolve()

    if not input_csv.is_file():
        print(f"Input file not found: {input_csv}", file=sys.stderr)
        sys.exit(1)

    output_csv.parent.mkdir(parents=True, exist_ok=True)

    processed = 0
    first_write = True

    reader = pd.read_csv(input_csv, chunksize=chunksize)
    for chunk in reader:
        if limit is not None and processed >= limit:
            break
        if limit is not None:
            remaining = limit - processed
            if remaining < len(chunk):
                chunk = chunk.iloc[:remaining].copy()

        intensities: list[float] = []
        moods: list[float] = []
        itexts: list[str] = []
        mtexts: list[str] = []
        xs: list[float] = []
        ys: list[float] = []

        if "lyrics" not in chunk.columns:
            print("Column 'lyrics' missing in preproccessed CSV.", file=sys.stderr)
            sys.exit(1)

        lyrics_list = chunk["lyrics"].fillna("").astype(str).tolist()
        valence_list = chunk["valence"].tolist() if "valence" in chunk.columns else [0.5] * len(chunk)
        energy_list = chunk["energy"].tolist() if "energy" in chunk.columns else [0.5] * len(chunk)

        n = len(chunk)
        for i in tqdm(
            range(n),
            total=n,
            desc=f"Ollama rows {processed + 1}-{processed + n}",
        ):
            li, lm, lit, lmt = score_lyrics_with_ollama(
                lyrics_list[i],
                LLM_MODEL,
                max_lyrics_chars=max_lyrics_chars,
                timeout=request_timeout,
            )
            x, y = coordinates_from_features(
                valence_list[i] if i < len(valence_list) else 0.5,
                energy_list[i] if i < len(energy_list) else 0.5,
                lm,
                li,
            )
            intensities.append(li)
            moods.append(lm)
            itexts.append(lit)
            mtexts.append(lmt)
            xs.append(x)
            ys.append(y)
            if sleep_s > 0:
                time.sleep(sleep_s)

        chunk = chunk.copy()
        chunk["lyrical_intensity"] = intensities
        chunk["lyrical_mood"] = moods
        chunk["lyrical_intensity_text"] = itexts
        chunk["lyrical_mood_text"] = mtexts
        chunk["x_coord"] = xs
        chunk["y_coord"] = ys

        chunk.to_csv(
            output_csv,
            mode="w" if first_write else "a",
            header=first_write,
            index=False,
        )
        first_write = False
        processed += len(chunk)

        if limit is not None and processed >= limit:
            break

    print(f"Wrote {processed} rows to {output_csv}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Ollama lyric scores + x/y from valence/energy averages.",
    )
    parser.add_argument(
        "input",
        nargs="?",
        type=Path,
        default=DEFAULT_INPUT_CSV,
        help=f"Input CSV (default: {DEFAULT_INPUT_CSV})",
    )
    parser.add_argument(
        "output",
        nargs="?",
        type=Path,
        default=DEFAULT_OUTPUT_CSV,
        help=f"Output CSV (default: {DEFAULT_OUTPUT_CSV})",
    )
    parser.add_argument(
        "--chunksize",
        type=int,
        default=5_000,
        help="Rows per pandas chunk when reading input.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Process at most this many rows (for testing).",
    )
    parser.add_argument(
        "--sleep",
        type=float,
        default=0.0,
        help="Seconds to sleep after each row (rate limiting).",
    )
    parser.add_argument(
        "--max-lyrics-chars",
        type=int,
        default=8000,
        help="Max characters of lyrics sent to the model per track.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=120.0,
        help="HTTP timeout per Ollama request (seconds).",
    )
    args = parser.parse_args()
    main(
        args.input,
        args.output,
        args.chunksize,
        args.limit,
        args.sleep,
        args.max_lyrics_chars,
        args.timeout,
    )
