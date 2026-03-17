#!/usr/bin/env python3
"""
Stage 2: HDBSCAN clustering of embeddings.

Supports two levels: deep (fine-grained) and wide (coarse).
Input: .npy embeddings. Output: .npy cluster labels per level.
"""

import argparse
import sys
import pickle
from pathlib import Path

import numpy as np
import hdbscan


def main():
    parser = argparse.ArgumentParser(description="HDBSCAN clustering of embeddings")
    parser.add_argument("input_embeddings", type=Path, help="Input .npy embeddings path")
    parser.add_argument("output_deep", type=Path, help="Output .npy deep cluster labels")
    parser.add_argument("output_wide", type=Path, help="Output .npy wide cluster labels")
    parser.add_argument("--input-metadata", type=Path, default=None,
                        help="Optional .pkl metadata to append clusters to DataFrame")
    parser.add_argument("--deep-min-cluster-size", type=int, default=50,
                        help="min_cluster_size for deep clustering")
    parser.add_argument("--deep-min-samples", type=int, default=15,
                        help="min_samples for deep clustering")
    parser.add_argument("--wide-min-cluster-size", type=int, default=500,
                        help="min_cluster_size for wide clustering")
    parser.add_argument("--wide-min-samples", type=int, default=100,
                        help="min_samples for wide clustering")
    args = parser.parse_args()

    if not args.input_embeddings.is_file():
        print(f"Error: file not found: {args.input_embeddings}", file=sys.stderr)
        sys.exit(1)

    print(f"Loading embeddings from {args.input_embeddings}...")
    embeddings = np.load(args.input_embeddings)
    print(f"Embeddings shape: {embeddings.shape}")

    print("Deep clustering (HDBSCAN)...")
    clusterer_deep = hdbscan.HDBSCAN(
        min_cluster_size=args.deep_min_cluster_size,
        min_samples=args.deep_min_samples,
        metric="euclidean",
        gen_min_span_tree=True,
    )
    labels_deep = clusterer_deep.fit_predict(embeddings)
    n_clusters_deep = len(set(labels_deep)) - (1 if -1 in labels_deep else 0)
    print(f"Deep: {n_clusters_deep} clusters, noise: {(labels_deep == -1).sum()}")

    print("Wide clustering (HDBSCAN)...")
    clusterer_wide = hdbscan.HDBSCAN(
        min_cluster_size=args.wide_min_cluster_size,
        min_samples=args.wide_min_samples,
        metric='euclidean',
        gen_min_span_tree=True
    )
    labels_wide = clusterer_wide.fit_predict(embeddings)
    n_clusters_wide = len(set(labels_wide)) - (1 if -1 in labels_wide else 0)
    print(f"Wide: {n_clusters_wide} clusters, noise: {(labels_wide == -1).sum()}")

    args.output_deep.parent.mkdir(parents=True, exist_ok=True)
    np.save(args.output_deep, labels_deep)
    print(f"Deep labels saved to {args.output_deep}")

    args.output_wide.parent.mkdir(parents=True, exist_ok=True)
    np.save(args.output_wide, labels_wide)
    print(f"Wide labels saved to {args.output_wide}")

    if args.input_metadata and args.input_metadata.is_file():
        print(f"Loading metadata from {args.input_metadata}...")
        with open(args.input_metadata, "rb") as f:
            df = pickle.load(f)
        df["deep_cluster"] = labels_deep
        df["wide_cluster"] = labels_wide
        output_meta = args.input_metadata.with_suffix(".with_clusters.pkl")
        with open(output_meta, "wb") as f:
            pickle.dump(df, f)
        print(f"Metadata with clusters saved to {output_meta}")

if __name__ == "__main__":
    main()