#!/usr/bin/env python3
"""
Stage 04: Embeddings -> UMAP -> HDBSCAN clustering -> t-SNE projection.

Input: preproccessed.csv (from stage 03).
Output: embeded_data.csv with x_coord, y_coord, cluster labels, and metadata.

Pipeline: embedding.py -> umap_reduce.py -> clustering.py -> visualize.py
"""

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

DEFAULT_MODEL = "nomic-ai/nomic-embed-text-v1.5"
DEFAULT_BATCH_SIZE = 16
DEFAULT_MIN_CLUSTER_SIZE = 50
DEFAULT_MIN_SAMPLES = 15
DEFAULT_PERPLEXITY = 30
DEFAULT_RANDOM_STATE = 42
DEFAULT_UMAP_COMPONENTS = 15
DEFAULT_UMAP_NEIGHBORS = 30
DEFAULT_UMAP_MIN_DIST = 0.0
DEFAULT_UMAP_METRIC = "cosine"


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
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Sentence-transformers model (default: Nomic embed v1.5)")
    parser.add_argument(
        "--no-audio-fusion",
        action="store_true",
        help="Text-only embeddings (do not concat Spotify audio columns from CSV)",
    )
    parser.add_argument(
        "--audio-fusion-scale",
        type=float,
        default=1.0,
        help="Weight on L2-normalized audio block after concat-prep (default 1.0)",
    )
    parser.add_argument(
        "--no-l2-modality-norm",
        action="store_true",
        help="Pass through to embedding.py: skip L2 per text/audio before concat",
    )
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument("--limit", type=int, default=None, help="Max rows to process (default: prompt or 1000)")
    parser.add_argument("--no-prompt", action="store_true", help="Skip interactive limit prompt")
    parser.add_argument("--min-cluster-size", type=int, default=DEFAULT_MIN_CLUSTER_SIZE)
    parser.add_argument("--min-samples", type=int, default=DEFAULT_MIN_SAMPLES)
    parser.add_argument("--perplexity", type=int, default=DEFAULT_PERPLEXITY)
    parser.add_argument("--random-state", type=int, default=DEFAULT_RANDOM_STATE)
    parser.add_argument("--umap-components", type=int, default=DEFAULT_UMAP_COMPONENTS)
    parser.add_argument("--umap-neighbors", type=int, default=DEFAULT_UMAP_NEIGHBORS)
    parser.add_argument("--umap-min-dist", type=float, default=DEFAULT_UMAP_MIN_DIST)
    parser.add_argument("--umap-metric", default=DEFAULT_UMAP_METRIC)
    parser.add_argument("--umap-normalize", action="store_true", help="L2-normalize embeddings before UMAP (see umap_reduce.py)")
    parser.add_argument(
        "--no-keep-intermediate",
        action="store_true",
        help="Delete intermediate embeddings.npy, umap_reduced.npy, metadata.pkl, labels_cluster.npy after run "
        "(default: keep them in stages/04_clustering/).",
    )
    parser.add_argument(
        "--cluster-only",
        action="store_true",
        help="Re-run HDBSCAN only: needs --from-umap and a CSV with the same row order (see --coords-from). "
        "Skips embeddings, UMAP, and t-SNE; updates cluster column in the CSV.",
    )
    parser.add_argument(
        "--from-umap",
        type=Path,
        default=None,
        help="With --cluster-only: path to umap_reduced.npy from a previous run (default pipeline keeps it in this folder).",
    )
    parser.add_argument(
        "--coords-from",
        type=Path,
        default=None,
        help="With --cluster-only: existing galaxy CSV (x/y/z coords) aligned with the UMAP rows. Default: same as --output.",
    )
    parser.add_argument(
        "--umap-only",
        action="store_true",
        help="Run only UMAP: write umap_reduced.npy (see --output-umap). "
        "Either provide --embeddings-npy or compute embeddings from --input (preproccessed.csv).",
    )
    parser.add_argument(
        "--embeddings-npy",
        type=Path,
        default=None,
        help="With --umap-only: skip embedding step; use this embeddings.npy as UMAP input.",
    )
    parser.add_argument(
        "--output-umap",
        type=Path,
        default=None,
        help="Destination for reduced vectors (default: <04_clustering>/umap_reduced.npy).",
    )
    args, _ = parser.parse_known_args()

    stage_dir = Path(__file__).resolve().parent
    output_csv = args.output.resolve()
    if args.cluster_only and args.umap_only:
        print("Error: use either --cluster-only or --umap-only, not both.", file=sys.stderr)
        sys.exit(1)

    if args.umap_only:
        umap_out = (args.output_umap or (stage_dir / "umap_reduced.npy")).resolve()

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

        emb_npy = args.embeddings_npy
        if emb_npy is None:
            input_csv = args.input.resolve()
            if not input_csv.is_file():
                print(f"Error: input not found: {input_csv}", file=sys.stderr)
                sys.exit(1)
            emb_file = stage_dir / "embeddings.npy"
            meta_file = stage_dir / "metadata.pkl"
            print(f"UMAP-only: embeddings from CSV, limit={'all' if limit == 0 else limit}.", flush=True)
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
            if args.no_audio_fusion:
                step1_args.append("--no-fuse-audio")
            step1_args.extend(["--audio-fusion-scale", str(args.audio_fusion_scale)])
            if args.no_l2_modality_norm:
                step1_args.append("--no-l2-modality-norm")
            run_script("embedding.py", step1_args, "Step 1: Sentence embeddings (for UMAP-only)")
        else:
            emb_file = emb_npy.resolve()
            if not emb_file.is_file():
                print(f"Error: embeddings not found: {emb_file}", file=sys.stderr)
                sys.exit(1)
            print(f"UMAP-only: using existing embeddings {emb_file}", flush=True)

        step_umap = [
            str(emb_file),
            str(umap_out),
            "--n-components",
            str(args.umap_components),
            "--n-neighbors",
            str(args.umap_neighbors),
            "--min-dist",
            str(args.umap_min_dist),
            "--metric",
            args.umap_metric,
            "--random-state",
            str(args.random_state),
        ]
        if args.umap_normalize:
            step_umap.append("--normalize")
        run_script("umap_reduce.py", step_umap, "UMAP-only: save umap_reduced.npy")

        print(f"\nDone (umap-only). Reduced vectors: {umap_out}")
        return

    if args.cluster_only:
        import numpy as np
        import pandas as pd

        umap_path = args.from_umap
        if umap_path is None:
            print("Error: --cluster-only requires --from-umap PATH (saved umap_reduced.npy).", file=sys.stderr)
            sys.exit(1)
        umap_path = umap_path.resolve()
        if not umap_path.is_file():
            print(f"Error: UMAP file not found: {umap_path}", file=sys.stderr)
            sys.exit(1)

        coords_csv = (args.coords_from or args.output).resolve()
        if not coords_csv.is_file():
            print(
                f"Error: CSV not found for --cluster-only: {coords_csv}\n"
                "Use --coords-from or run the full stage once to produce embeded_data.csv.",
                file=sys.stderr,
            )
            sys.exit(1)

        vecs = np.load(umap_path)
        n_umap = len(vecs)
        df = pd.read_csv(coords_csv)
        if len(df) != n_umap:
            print(
                f"Error: row count mismatch: {umap_path} has {n_umap} rows, {coords_csv} has {len(df)}. "
                "UMAP and CSV must come from the same indexing.",
                file=sys.stderr,
            )
            sys.exit(1)

        temp_dir = Path(tempfile.mkdtemp(prefix="cluster_only_"))
        labels_file = temp_dir / "labels_cluster.npy"
        try:
            step2_args = [
                str(umap_path),
                str(labels_file),
                "--min-cluster-size",
                str(args.min_cluster_size),
                "--min-samples",
                str(args.min_samples),
            ]
            run_script("clustering.py", step2_args, "HDBSCAN only (reuse UMAP, skip t-SNE)")

            df["cluster"] = np.load(labels_file)
            if "energy" in df.columns and "lyrical_intensity" not in df.columns:
                df["lyrical_intensity"] = df["energy"].fillna(0.5)
            if "valence" in df.columns and "lyrical_mood" not in df.columns:
                df["lyrical_mood"] = df["valence"].fillna(0.5)
            output_csv.parent.mkdir(parents=True, exist_ok=True)
            df.to_csv(output_csv, index=False)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

        print(f"\nDone (cluster-only). Updated clusters in {output_csv}")
        return

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

    if args.no_keep_intermediate:
        temp_dir = Path(tempfile.mkdtemp(prefix="clustering_"))
        emb_file = temp_dir / "embeddings.npy"
        umap_file = temp_dir / "umap_reduced.npy"
        meta_file = temp_dir / "metadata.pkl"
        labels_file = temp_dir / "labels_cluster.npy"
    else:
        temp_dir = None
        emb_file = stage_dir / "embeddings.npy"
        umap_file = stage_dir / "umap_reduced.npy"
        meta_file = stage_dir / "metadata.pkl"
        labels_file = stage_dir / "labels_cluster.npy"

    try:
        # Step 1: Sentence embeddings
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
        if args.no_audio_fusion:
            step1_args.append("--no-fuse-audio")
        step1_args.extend(["--audio-fusion-scale", str(args.audio_fusion_scale)])
        if args.no_l2_modality_norm:
            step1_args.append("--no-l2-modality-norm")
        run_script("embedding.py", step1_args, "Step 1: Sentence embeddings")

        # Step 2: UMAP reduction
        step_umap = [
            str(emb_file),
            str(umap_file),
            "--n-components",
            str(args.umap_components),
            "--n-neighbors",
            str(args.umap_neighbors),
            "--min-dist",
            str(args.umap_min_dist),
            "--metric",
            args.umap_metric,
            "--random-state",
            str(args.random_state),
        ]
        if args.umap_normalize:
            step_umap.append("--normalize")
        run_script("umap_reduce.py", step_umap, "Step 2: UMAP reduction")

        # Step 3: HDBSCAN on UMAP coordinates
        step2_args = [
            str(umap_file),
            str(labels_file),
            "--min-cluster-size",
            str(args.min_cluster_size),
            "--min-samples",
            str(args.min_samples),
        ]
        run_script("clustering.py", step2_args, "Step 3: HDBSCAN clustering")

        # Step 4: t-SNE on UMAP vectors (2D map)
        step3_args = [
            str(umap_file),
            str(output_csv),
            "--cluster-labels",
            str(labels_file),
            "--input-metadata",
            str(meta_file),
            "--perplexity",
            str(args.perplexity),
            "--random-state",
            str(args.random_state),
        ]
        run_script("visualize.py", step3_args, "Step 4: t-SNE projection")

        # Add lyrical_intensity/lyrical_mood fallbacks for frontend color mapping
        import pandas as pd

        df = pd.read_csv(output_csv)
        if "energy" in df.columns and "lyrical_intensity" not in df.columns:
            df["lyrical_intensity"] = df["energy"].fillna(0.5)
        if "valence" in df.columns and "lyrical_mood" not in df.columns:
            df["lyrical_mood"] = df["valence"].fillna(0.5)
        df.to_csv(output_csv, index=False)

    finally:
        if args.no_keep_intermediate and temp_dir is not None and temp_dir.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)
            print("Temporary files removed.")

    print(f"\nDone. Output saved to {output_csv}")


def desc():
    return (
        "Embeddings -> UMAP -> HDBSCAN -> t-SNE: preproccessed.csv -> embeded_data.csv. "
        "--umap-only writes umap_reduced.npy; --cluster-only --from-umap refreshes HDBSCAN without UMAP/t-SNE."
    )


if __name__ == "__main__":
    main()
