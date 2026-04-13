#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Reduce high-dimensional sentence embeddings with UMAP before clustering / t-SNE.

Inputs / outputs:
- Input: embeddings.npy with shape (N, D) (e.g. sentence-transformers vectors).
- Output: umap_reduced.npy with shape (N, n_components) (default n_components=15).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import umap
from sklearn.preprocessing import normalize


def main() -> None:
    # CLI: define all parameters needed for reproducible UMAP reduction.
    # Positional: input embeddings file path.
    # Positional: output reduced vectors file path.
    # Target low dimensionality (15 is a common default).
    # UMAP neighborhood size controls local vs global structure emphasis.
    # min_dist controls how tightly points can pack in the embedding space.
    # Distance metric for UMAP (cosine is common for text embeddings).
    # Random seed for reproducibility (same seed -> more stable results).
    # Optional L2 row normalization before UMAP (sometimes helps stability).
    parser = argparse.ArgumentParser(description="UMAP dimensionality reduction for embeddings")
    parser.add_argument("input_embeddings", type=Path, help="Input .npy array (N, D)")
    parser.add_argument("output_reduced", type=Path, help="Output .npy array (N, n_components)")
    parser.add_argument("--n-components", type=int, default=15, help="Target dimensions (default 15)")
    parser.add_argument("--n-neighbors", type=int, default=15, help="UMAP n_neighbors")
    parser.add_argument("--min-dist", type=float, default=0.0, help="UMAP min_dist")
    parser.add_argument("--metric", default="cosine", help="UMAP metric (e.g. cosine, euclidean)")    
    parser.add_argument("--random-state", type=int, default=42, help="Random seed")
    parser.add_argument("--normalize", action="store_true", help="L2-normalize embedding rows before UMAP")
    args = parser.parse_args()

    # Validate input file exists.
    path_in = args.input_embeddings
    if not path_in.is_file():
        print(f"Error: file not found: {path_in}", file=sys.stderr)
        sys.exit(1)

    # Load embeddings matrix from disk.
    print(f"Loading {path_in}...", flush=True)
    embeddings = np.load(path_in)

    # Ensure we have a 2D matrix (N samples, D dims).
    if embeddings.ndim != 2:
        print(f"Error: expected 2D array, got shape {embeddings.shape}", file=sys.stderr)
        sys.exit(1)

    n = len(embeddings)

    # UMAP requires at least 2 samples to fit a meaningful embedding.
    if n < 2:
        print("Error: need at least 2 samples for UMAP.", file=sys.stderr)
        sys.exit(1)

    # Work in float64 for numerical stability during UMAP fit.
    x = embeddings.astype(np.float64, copy=False)

    # Optionally normalize each row to unit L2 norm.
    if args.normalize:
        x = normalize(x, axis=1, norm="l2")

    # Guardrail: n_components cannot exceed input dimensionality or (n-1).
    n_comp = min(args.n_components, x.shape[1], max(1, n - 1))
    if n_comp < args.n_components:
        print(
            f"Warning: n_components reduced to {n_comp} (limited by D and/or sample count).",
            flush=True,
        )

    # Guardrail: n_neighbors cannot exceed (n-1) and must be at least 2 for UMAP.
    n_neighbors = min(args.n_neighbors, max(2, n - 1))

    # Log key hyperparameters before fitting (helps debugging pipelines).
    print(
        f"Running UMAP: n_samples={n}, dim_in={x.shape[1]}, "
        f"n_components={n_comp}, n_neighbors={n_neighbors}, metric={args.metric!r}...",
        flush=True,
    )

    # Fit UMAP on the full batch dataset and transform all rows.
    reducer = umap.UMAP(
        n_neighbors=n_neighbors,
        n_components=n_comp,
        min_dist=args.min_dist,
        metric=args.metric,
        random_state=args.random_state,
        verbose=True,
    )
    reduced = reducer.fit_transform(x)

    print(f"Reduced shape: {reduced.shape}", flush=True)

    # Save reduced vectors as float32.
    args.output_reduced.parent.mkdir(parents=True, exist_ok=True)
    np.save(args.output_reduced, reduced.astype(np.float32))
    print(f"Saved reduced vectors: {args.output_reduced}", flush=True)


if __name__ == "__main__":
    main()