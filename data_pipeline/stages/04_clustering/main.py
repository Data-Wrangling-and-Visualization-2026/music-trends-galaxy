#!/usr/bin/env python3
"""
Stage 04: Embeddings -> HDBSCAN clustering -> t-SNE projection.

Input: preproccessed.csv (from stage 03).
Output: embeded_data.csv with x_coord, y_coord, cluster labels, and metadata.

Pipeline: embedding.py -> clustering.py -> visualize.py
"""

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

DEFAULT_MODEL = "all-MiniLM-L6-v2"
DEFAULT_BATCH_SIZE = 32
DEFAULT_DEEP_MIN_CLUSTER = 50
DEFAULT_DEEP_MIN_SAMPLES = 15
DEFAULT_WIDE_MIN_CLUSTER = 500
DEFAULT_WIDE_MIN_SAMPLES = 100
DEFAULT_PERPLEXITY = 30
DEFAULT_RANDOM_STATE = 42


def run_script(script_name: str, args_list: list[str], desc: str) -> None:
    """Run a Python script in this directory with given arguments."""
    stage_dir = Path(__file__).resolve().parent
    script_path = stage_dir / script_name
    if not script_path.is_file():
        print(f"Error: script not found: {script_path}", file=sys.stderr)
        sys.exit(1)
    cmd = [sys.executable, str(script_path)] + args_list
    print(f"\n=== {desc} ===")
    print(f"Running: {' '.join(cmd)}")
    subprocess.run(cmd, check=True, cwd=str(stage_dir))


def main(cxt=None):
    """Run full clustering pipeline: preproccessed.csv -> embeded_data.csv."""
    if cxt is not None:
        storage = cxt.get_storage_dir()
        input_csv = storage / "preproccessed.csv"
        output_csv = storage / "embeded_data.csv"
    else:
        storage = (Path(__file__).resolve().parents[3] / "storage").resolve()
        input_csv = storage / "preproccessed.csv"
        output_csv = storage / "embeded_data.csv"

    parser = argparse.ArgumentParser(description="Clustering: preproccessed -> embeded_data")
    parser.add_argument("--input", type=Path, default=input_csv, help="Input preproccessed.csv")
    parser.add_argument("--output", type=Path, default=output_csv, help="Output embeded_data.csv")
    parser.add_argument("--text-col", default="lyrics", help="Text column for embeddings")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Sentence-transformers model")
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument("--limit", type=int, default=None, help="Max rows to process (default: prompt or 1000)")
    parser.add_argument("--no-prompt", action="store_true", help="Skip interactive limit prompt")
    parser.add_argument("--deep-min-cluster", type=int, default=DEFAULT_DEEP_MIN_CLUSTER)
    parser.add_argument("--deep-min-samples", type=int, default=DEFAULT_DEEP_MIN_SAMPLES)
    parser.add_argument("--wide-min-cluster", type=int, default=DEFAULT_WIDE_MIN_CLUSTER)
    parser.add_argument("--wide-min-samples", type=int, default=DEFAULT_WIDE_MIN_SAMPLES)
    parser.add_argument("--perplexity", type=int, default=DEFAULT_PERPLEXITY)
    parser.add_argument("--random-state", type=int, default=DEFAULT_RANDOM_STATE)
    parser.add_argument("--keep-intermediate", action="store_true", help="Keep .npy and .pkl files")
    args, _ = parser.parse_known_args()

    # Limit: from run.py --limit, env PIPELINE_LIMIT, or interactive prompt
    limit = args.limit
    if limit is None and cxt is not None and hasattr(cxt, "limit") and cxt.limit is not None:
        limit = cxt.limit
    if limit is None:
        limit = __import__("os").environ.get("PIPELINE_LIMIT")
        limit = int(limit) if limit and limit.isdigit() else None
    if limit is None and not args.no_prompt and sys.stdin.isatty():
        prompt = "Max tracks to process (0=all, default 1000): "
        try:
            inp = input(prompt).strip() or "1000"
            limit = 0 if inp == "0" else max(1, int(inp))
        except (ValueError, EOFError):
            limit = 1000
    if limit is None:
        limit = 1000
    args.limit = limit
    print(f"Processing {'all' if limit == 0 else limit} tracks.", flush=True)

    input_csv = args.input.resolve()
    output_csv = args.output.resolve()

    if not input_csv.is_file():
        print(f"Error: input not found: {input_csv}", file=sys.stderr)
        sys.exit(1)

    stage_dir = Path(__file__).resolve().parent
    temp_dir = Path(tempfile.mkdtemp(prefix="clustering_"))
    emb_file = temp_dir / "embeddings.npy"
    meta_file = temp_dir / "metadata.pkl"
    deep_file = temp_dir / "labels_deep.npy"
    wide_file = temp_dir / "labels_wide.npy"

    if args.keep_intermediate:
        emb_file = stage_dir / "embeddings.npy"
        meta_file = stage_dir / "metadata.pkl"
        deep_file = stage_dir / "labels_deep.npy"
        wide_file = stage_dir / "labels_wide.npy"

    try:
        # Step 1: Embeddings
        step1_args = [
            str(input_csv),
            str(emb_file),
            "--output-metadata",
            str(meta_file),
            "--text-column",
            args.text_col,
            "--model",
            args.model,
            "--batch-size",
            str(args.batch_size),
        ]
        if args.limit:
            step1_args.extend(["--limit", str(args.limit)])
        run_script("embedding.py", step1_args, "Step 1: Embeddings")

        # Step 2: Clustering
        step2_args = [
            str(emb_file),
            str(deep_file),
            str(wide_file),
            "--deep-min-cluster-size",
            str(args.deep_min_cluster),
            "--deep-min-samples",
            str(args.deep_min_samples),
            "--wide-min-cluster-size",
            str(args.wide_min_cluster),
            "--wide-min-samples",
            str(args.wide_min_samples),
        ]
        run_script("clustering.py", step2_args, "Step 2: HDBSCAN clustering")

        # Step 3: t-SNE visualization
        step3_args = [
            str(emb_file),
            str(output_csv),
            "--deep-labels",
            str(deep_file),
            "--wide-labels",
            str(wide_file),
            "--input-metadata",
            str(meta_file),
            "--perplexity",
            str(args.perplexity),
            "--random-state",
            str(args.random_state),
        ]
        run_script("visualize.py", step3_args, "Step 3: t-SNE projection")

        # Add lyrical_intensity/lyrical_mood fallbacks for frontend color mapping
        import pandas as pd

        df = pd.read_csv(output_csv)
        if "energy" in df.columns and "lyrical_intensity" not in df.columns:
            df["lyrical_intensity"] = df["energy"].fillna(0.5)
        if "valence" in df.columns and "lyrical_mood" not in df.columns:
            df["lyrical_mood"] = df["valence"].fillna(0.5)
        df.to_csv(output_csv, index=False)

    finally:
        if not args.keep_intermediate and temp_dir.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)
            print("Temporary files removed.")

    print(f"\nDone. Output saved to {output_csv}")


def desc():
    return "Embeddings -> HDBSCAN -> t-SNE: preproccessed.csv -> embeded_data.csv."


if __name__ == "__main__":
    main()
