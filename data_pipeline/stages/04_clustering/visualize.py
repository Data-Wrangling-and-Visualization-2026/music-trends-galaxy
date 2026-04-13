#!/usr/bin/env python3
"""
t-SNE projection to 3D for the galaxy map.

Input: low-dimensional vectors (UMAP-reduced (N, 15)).
"""

import argparse
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.manifold import TSNE


def main():
    parser = argparse.ArgumentParser(
        description="t-SNE 3D projection (expects UMAP-reduced or similar (N, D_low) array)"
    )
    parser.add_argument(
        "input_vectors",
        type=Path,
        help="Input .npy path: (N, D) with small D (e.g. UMAP output), not raw sentence embeddings",
    )
    parser.add_argument("output_csv", type=Path, help="Output CSV path")
    parser.add_argument(
        "--cluster-labels",
        type=Path,
        default=None,
        help="Optional .npy cluster labels (one row per input vector)",
    )
    parser.add_argument(
        "--input-metadata",
        type=Path,
        default=None,
        help="Optional .pkl metadata to merge with coordinates",
    )
    parser.add_argument("--perplexity", type=float, default=30.0, help="t-SNE perplexity")
    parser.add_argument("--random-state", type=int, default=42, help="Random seed")
    parser.add_argument(
        "--sample-size",
        type=int,
        default=None,
        help="If set, use random subsample for faster t-SNE",
    )
    parser.add_argument(
        "--scale",
        type=float,
        default=10.0,
        help="Multiply all three coordinates by this factor (widen the cloud)",
    )
    args = parser.parse_args()

    if not args.input_vectors.is_file():
        print(f"Error: file not found: {args.input_vectors}", file=sys.stderr)
        sys.exit(1)

    print(f"Loading vectors from {args.input_vectors}...", flush=True)
    embeddings = np.load(args.input_vectors)
    print(f"Shape: {embeddings.shape}", flush=True)

    if args.sample_size is not None and len(embeddings) > args.sample_size:
        print(f"Using random subsample of {args.sample_size} rows for faster t-SNE.")
        indices = np.random.choice(len(embeddings), args.sample_size, replace=False)
        embeddings_sample = embeddings[indices]
        use_subset = True
    else:
        indices = None
        embeddings_sample = embeddings
        use_subset = False

    n_sample = len(embeddings_sample)
    perplexity = (
        min(args.perplexity, n_sample - 1) if n_sample < args.perplexity + 1 else args.perplexity
    )
    if perplexity < 5:
        perplexity = min(5, max(1, n_sample - 1))
    perplexity = float(max(1.0, min(perplexity, max(1.0, float(n_sample - 1)))))

    print(f"Running t-SNE 3D (perplexity={perplexity})...", flush=True)
    tsne = TSNE(
        n_components=3,
        perplexity=perplexity,
        random_state=args.random_state,
        verbose=1,
        init="pca",
        learning_rate="auto",
    )
    coords = tsne.fit_transform(embeddings_sample)
    print("t-SNE done.")

    if args.scale != 1.0:
        coords = coords * args.scale

    cols = {
        "x_coord": coords[:, 0],
        "y_coord": coords[:, 1],
        "z_coord": coords[:, 2],
    }

    if use_subset:
        result_df = pd.DataFrame(cols)
        if args.cluster_labels and args.cluster_labels.is_file():
            cl = np.load(args.cluster_labels)
            result_df["cluster"] = cl[indices]
        if args.input_metadata and args.input_metadata.is_file():
            with open(args.input_metadata, "rb") as f:
                df_meta = pickle.load(f)
            result_df = pd.concat([df_meta.iloc[indices].reset_index(drop=True), result_df], axis=1)
    else:
        result_df = pd.DataFrame(cols)
        if args.cluster_labels and args.cluster_labels.is_file():
            result_df["cluster"] = np.load(args.cluster_labels)
        if args.input_metadata and args.input_metadata.is_file():
            with open(args.input_metadata, "rb") as f:
                df_meta = pickle.load(f)
            result_df = pd.concat([df_meta.reset_index(drop=True), result_df], axis=1)

    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    result_df.to_csv(args.output_csv, index=False)
    print(f"Saved to {args.output_csv}")


if __name__ == "__main__":
    main()
