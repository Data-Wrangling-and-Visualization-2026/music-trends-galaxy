"""
Normalize Spotify-style audio columns from preprocessed CSV for concatenation with text embeddings.

Order matches backend ``fact_track_audio_features`` / ``_pick_audio``.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

AUDIO_KEYS = [
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
    "time_signature",
]


def count_audio_columns(df: pd.DataFrame) -> int:
    return sum(1 for c in AUDIO_KEYS if c in df.columns)


def normalized_audio_block(df: pd.DataFrame, scale: float = 1.0) -> np.ndarray:
    """Shape (N, len(AUDIO_KEYS)), values in ~[0, 1] per feature family."""
    n = len(df)
    out = np.zeros((n, len(AUDIO_KEYS)), dtype=np.float32)
    for j, key in enumerate(AUDIO_KEYS):
        if key not in df.columns:
            out[:, j] = 0.5
            continue
        v = pd.to_numeric(df[key], errors="coerce").to_numpy()
        if key in (
            "danceability",
            "energy",
            "speechiness",
            "acousticness",
            "instrumentalness",
            "liveness",
            "valence",
        ):
            out[:, j] = np.clip(np.nan_to_num(v, nan=0.5), 0.0, 1.0)
        elif key == "key":
            out[:, j] = np.clip(np.nan_to_num(v, nan=5.5) / 11.0, 0.0, 1.0)
        elif key == "loudness":
            out[:, j] = np.clip((np.nan_to_num(v, nan=-30.0) + 60.0) / 60.0, 0.0, 1.0)
        elif key == "mode":
            out[:, j] = np.clip(np.nan_to_num(v, nan=0.5), 0.0, 1.0)
        elif key == "tempo":
            out[:, j] = np.clip(np.nan_to_num(v, nan=120.0) / 200.0, 0.0, 1.0)
        elif key == "time_signature":
            out[:, j] = np.clip((np.nan_to_num(v, nan=4.0) - 3.0) / 5.0, 0.0, 1.0)
    if scale != 1.0:
        out *= np.float32(scale)
    return out


def maybe_fused_audio(
    df: pd.DataFrame,
    *,
    fuse: bool,
    scale: float,
) -> np.ndarray | None:
    if not fuse:
        return None
    n_ok = count_audio_columns(df)
    if n_ok == 0:
        print(
            "Warning: no Spotify audio columns in CSV; using text-only vector (no concat).",
            flush=True,
        )
        return None
    if n_ok < len(AUDIO_KEYS):
        print(
            f"Warning: {n_ok}/{len(AUDIO_KEYS)} audio columns found; missing filled with 0.5 neutral.",
            flush=True,
        )
    return normalized_audio_block(df, scale=scale)
