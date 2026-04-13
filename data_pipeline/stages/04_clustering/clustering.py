#!/usr/bin/env python3
"""
Stage 2: HDBSCAN clustering of UMAP-reduced vectors (or any fixed-length vectors).

One cluster assignment per point (single HDBSCAN run).
Input: .npy array (N, D) — typically UMAP output from umap_reduce.py.
Output: .npy cluster labels (integers; -1 = noise).

По умолчанию (без аргументов) читает ``umap_reduced.npy`` и пишет ``labels_cluster.npy``
в каталоге этого этапа (``04_clustering/``).
"""

import argparse
import pickle
import sys
from pathlib import Path

import hdbscan
import numpy as np

_STAGE_DIR = Path(__file__).resolve().parent
_DEFAULT_UMAP = _STAGE_DIR / "umap_reduced.npy"
_DEFAULT_LABELS = _STAGE_DIR / "labels_cluster.npy"


def print_cluster_track_counts(labels: np.ndarray) -> None:
    """Print cluster count and number of tracks per label (-1 = noise)."""
    lab = np.asarray(labels).ravel()
    uniq, counts = np.unique(lab, return_counts=True)
    n_clusters = len(uniq) - (1 if -1 in uniq else 0)
    print(f"Clusters (excluding noise label -1): {n_clusters}")
    print("Tracks per label:")
    for u, c in zip(uniq, counts):
        name = "noise" if int(u) == -1 else str(int(u))
        print(f"  {name}: {int(c)}")


def main():
    parser = argparse.ArgumentParser(
        description="HDBSCAN clustering of reduced embeddings",
        epilog=(
            "Examples:\n"
            "  python clustering.py\n"
            "  python clustering.py path/to/umap_reduced.npy\n"
            "  python clustering.py in.npy out_labels.npy\n"
            f"Defaults: input {_DEFAULT_UMAP.name}, output {_DEFAULT_LABELS.name} in {_STAGE_DIR}"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "input_vectors",
        type=Path,
        nargs="?",
        default=_DEFAULT_UMAP,
        help=f"Input .npy (N, D), e.g. UMAP output (default: {_DEFAULT_UMAP})",
    )
    parser.add_argument(
        "output_labels",
        type=Path,
        nargs="?",
        default=_DEFAULT_LABELS,
        help=f"Output cluster labels .npy (default: {_DEFAULT_LABELS})",
    )
    parser.add_argument(
        "--input-metadata",
        type=Path,
        default=None,
        help="Optional .pkl metadata to append cluster column to DataFrame",
    )
    parser.add_argument(
        "--min-cluster-size",
        type=int,
        default=50,
        help="HDBSCAN min_cluster_size",
    )
    parser.add_argument(
        "--min-samples",
        type=int,
        default=15,
        help="HDBSCAN min_samples",
    )
    args = parser.parse_args()

    if not args.input_vectors.is_file():
        print(f"Error: file not found: {args.input_vectors}", file=sys.stderr)
        sys.exit(1)

    print(f"Loading vectors from {args.input_vectors}...")
    embeddings = np.load(args.input_vectors)
    print(f"Shape: {embeddings.shape}")

    print("Clustering (HDBSCAN)...")
    clusterer = hdbscan.HDBSCAN(
        min_cluster_size=args.min_cluster_size,
        min_samples=args.min_samples,
        metric="euclidean",
        gen_min_span_tree=True,
    )
    labels = clusterer.fit_predict(embeddings)
    n_clusters = len(set(labels)) - (1 if -1 in labels else 0)
    print(f"Found {n_clusters} clusters, noise points: {(labels == -1).sum()}")

    args.output_labels.parent.mkdir(parents=True, exist_ok=True)
    np.save(args.output_labels, labels)
    print(f"Labels saved to {args.output_labels}")

    if args.input_metadata and args.input_metadata.is_file():
        print(f"Loading metadata from {args.input_metadata}...")
        with open(args.input_metadata, "rb") as f:
            df = pickle.load(f)
        df["cluster"] = labels
        output_meta = args.input_metadata.with_suffix(".with_clusters.pkl")
        with open(output_meta, "wb") as f:
            pickle.dump(df, f)
        print(f"Metadata with clusters saved to {output_meta}")

    print_cluster_track_counts(labels)


if __name__ == "__main__":
    main()
