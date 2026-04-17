# -*- coding: utf-8 -*-
"""
Shared constants and helpers for stage-05 LLM annotation scripts.

embeded_data.csv (stage 04) includes a ``cluster`` column with HDBSCAN labels; stage 05
cluster LLM output is ``cluster_descriptions.json`` (not split by level).
"""

from __future__ import annotations

import ast
import json
import math
import os
import re
from pathlib import Path
from typing import Any, Optional, Tuple

import pandas as pd
import requests

# Four numeric features from the embedding/clustering CSV.
METRIC_COLUMNS: tuple[str, ...] = (
    "lyrical_intensity",
    "lyrical_mood",
    "energy",
    "valence",
)

_REPO_ROOT: Path = Path(__file__).resolve().parents[3]
STORAGE_DIR: Path = Path(os.getenv("STORAGE_DIR", str(_REPO_ROOT / "storage"))).resolve()

DEFAULT_EMBEDED_CSV: Path = STORAGE_DIR / "embeded_data.csv"
DEFAULT_PREPROCESSED_CSV: Path = STORAGE_DIR / "preproccessed.csv"

OLLAMA_GENERATE_URL: str = os.getenv(
    "OLLAMA_GENERATE_URL",
    "http://localhost:11434/api/generate",
)

LLM_MODEL: str = os.getenv("LLM_MODEL", "llama3")


def is_noise_cluster_label(code: Any) -> bool:
    """True for HDBSCAN noise (-1) and common sentinel labels; never send these to the LLM."""
    s = str(code).strip()
    if not s:
        return True
    low = s.lower()
    if low in ("noise", "nan", "none"):
        return True
    if low == "-1":
        return True
    try:
        if int(float(s)) == -1:
            return True
    except ValueError:
        pass
    return False


def cluster_label_as_number(code: Any) -> Optional[int]:
    """Integer cluster id when the label is numeric (e.g. 0, 1, 2); else None."""
    try:
        return int(float(str(code).strip()))
    except ValueError:
        return None


def sample_lyrics_lines_by_fraction(text: str, frac: float) -> str:
    """
    Keep about ``frac`` of lines, spread from start to end (fewer tokens → faster Ollama).
    ``frac`` in (0, 1]; 1.0 returns text unchanged.
    """
    if frac >= 1.0 - 1e-12:
        return text
    s = (text or "").strip()
    if not s:
        return ""
    lines = s.splitlines()
    n = len(lines)
    if n <= 1:
        return s
    k = max(1, math.ceil(n * frac))
    if k >= n:
        return s
    if k == 1:
        return lines[n // 2]
    picked = [lines[int(round(j * (n - 1) / (k - 1)))] for j in range(k)]
    return "\n".join(picked)


def parse_artist_ids(cell: Any) -> list[str]:
    """Parse artist_ids from preprocessed (JSON list or Python list string)."""
    if cell is None or (isinstance(cell, float) and pd.isna(cell)):
        return []
    s = str(cell).strip()
    if not s or s.lower() == "nan":
        return []
    try:
        v = json.loads(s)
        if isinstance(v, list):
            return [str(x).strip() for x in v if str(x).strip()]
    except Exception:
        pass
    try:
        v = ast.literal_eval(s)
        if isinstance(v, list):
            return [str(x).strip() for x in v if str(x).strip()]
    except Exception:
        pass
    return []


def load_merged_embeded_preprocessed(embeded_path: Path, pre_path: Path) -> pd.DataFrame:
    """Inner-join embeded_data with preprocessed on track id."""
    emb = pd.read_csv(embeded_path, encoding="utf-8-sig", low_memory=False)
    pre = pd.read_csv(pre_path, encoding="utf-8-sig", low_memory=False)
    emb["id"] = emb["id"].astype(str)
    pre["id"] = pre["id"].astype(str)
    base_pre = ["name", "artists", "artist_ids", "album", "album_id", "lyrics"]
    use_pre = ["id"] + [c for c in base_pre if c in pre.columns]
    pre_sub = pre[use_pre]
    return emb.merge(pre_sub, on="id", how="inner", suffixes=("", "_pre"))


def aggregate_metric_stats(df: pd.DataFrame) -> dict[str, dict[str, Optional[float]]]:
    """
    Min / max / mean over the given row subset.
    """
    out: dict[str, dict[str, Optional[float]]] = {}
    for col in METRIC_COLUMNS:
        if col not in df.columns:
            out[col] = {"min": None, "max": None, "mean": None}
            continue
        s = pd.to_numeric(df[col], errors="coerce").dropna()
        if s.empty:
            out[col] = {"min": None, "max": None, "mean": None}
            continue
        out[col] = {
            "min": round(float(s.min()), 4),
            "max": round(float(s.max()), 4),
            "mean": round(float(s.mean()), 4),
        }
    return out


def parse_llm_json(raw: str) -> dict[str, Any]:
    raw = raw.strip()
    if not raw:
        return {}
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


def format_stats_for_prompt(stats: dict[str, dict[str, Optional[float]]]) -> str:
    lines = []
    for key in METRIC_COLUMNS:
        d = stats.get(key, {})
        mn, mx, mu = d.get("min"), d.get("max"), d.get("mean")
        lines.append(f"- {key}: min={mn}, max={mx}, mean={mu}")
    return "\n".join(lines)


def ollama_description_en(*, prompt: str, timeout: float) -> str:
    """One request to Ollama, expecting JSON with description or description_en."""
    payload = {
        "model": LLM_MODEL,
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
        desc = parsed.get("description_en") or parsed.get("description")
        return str(desc or "").strip() or "—"
    except Exception as e:
        return f"[LLM error: {type(e).__name__}: {e}]"


def normalize_two_word_title(raw: str) -> str:
    """Reduce model output to exactly two whitespace-separated tokens."""
    s = (raw or "").strip()
    if not s:
        return "Unnamed Cluster"
    parts = re.findall(r"\S+", s)
    if len(parts) >= 2:
        return f"{parts[0]} {parts[1]}"
    if len(parts) == 1:
        return f"{parts[0]} Mix"
    return "Unnamed Cluster"


def ollama_cluster_name_and_description(*, prompt: str, timeout: float) -> Tuple[str, str]:
    """Ollama JSON with 'name' (two-word title) and 'description' / 'description_en'."""
    payload = {
        "model": LLM_MODEL,
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
        raw_name = parsed.get("name") or parsed.get("short_title") or parsed.get("title") or ""
        name = normalize_two_word_title(str(raw_name))
        desc = parsed.get("description_en") or parsed.get("description")
        desc_s = str(desc or "").strip() or "—"
        return name, desc_s
    except Exception as e:
        err = f"[LLM error: {type(e).__name__}: {e}]"
        return "Error Title", err
