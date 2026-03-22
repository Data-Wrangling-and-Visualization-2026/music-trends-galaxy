#!/usr/bin/env python3
"""
Stage 03: Normalize pipeline output to preproccessed.csv format.

Converts output.csv into preproccessed.csv: fixed column order, lyrics without
LRC timestamps, empty lyrics_path. Invokes preprocess_output.
"""

from pathlib import Path

from preprocess_output import main as run_preprocess

DEFAULT_CHUNKSIZE = 10_000


def main(cxt=None):
    """Run preprocess: output.csv -> preproccessed.csv."""
    if cxt is not None:
        storage = cxt.get_storage_dir()
        input_csv = storage / "output.csv"
        output_csv = storage / "preproccessed.csv"
    else:
        storage = (Path(__file__).resolve().parents[3] / "storage").resolve()
        input_csv = storage / "output.csv"
        output_csv = storage / "preproccessed.csv"

    run_preprocess(input_csv, output_csv, DEFAULT_CHUNKSIZE)


def desc():
    return "Convert output.csv to preproccessed.csv (clean lyrics, fixed columns)."
