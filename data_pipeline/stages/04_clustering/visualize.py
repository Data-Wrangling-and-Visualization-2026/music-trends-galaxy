#!/usr/bin/env python3
"""
Stage 3: t-SNE visualization.

Input: embeddings (.npy), optional cluster labels (.npy).
Output: CSV with x_coord, y_coord and cluster labels.
"""

import argparse
import sys
import pickle
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.manifold import TSNE

def main():
    parser = argparse.ArgumentParser(description="t-SNE visualization of embeddings")
    parser.add_argument("input_embeddings", type=Path, help="Input .npy embeddings path")
    parser.add_argument("output_csv", type=Path, help="Output CSV path")
    parser.add_argument("--deep-labels", type=Path, default=None, help="Optional .npy deep cluster labels")
    parser.add_argument("--wide-labels", type=Path, default=None, help="Optional .npy wide cluster labels")
    parser.add_argument("--input-metadata", type=Path, default=None,
                        help="Optional .pkl metadata to merge with coordinates")
    parser.add_argument("--perplexity", type=float, default=30.0, help="t-SNE perplexity")
    parser.add_argument("--random-state", type=int, default=42, help="Random seed")
    parser.add_argument("--sample-size", type=int, default=None,
                        help="If set, use random subsample for faster t-SNE")
    args = parser.parse_args()

    if not args.input_embeddings.is_file():
        print(f"Error: file not found: {args.input_embeddings}", file=sys.stderr)
        sys.exit(1)

    print(f"Loading embeddings from {args.input_embeddings}...")
    embeddings = np.load(args.input_embeddings)
    print(f"Embeddings shape: {embeddings.shape}")

    if args.sample_size is not None and len(embeddings) > args.sample_size:
        print(f"Using random subsample of {args.sample_size} rows for faster t-SNE.")
        indices = np.random.choice(len(embeddings), args.sample_size, replace=False)
        embeddings_sample = embeddings[indices]
        use_subset = True
    else:
        indices = None
        embeddings_sample = embeddings
        use_subset = False

    print("Running t-SNE...")
    tsne = TSNE(n_components=2, perplexity=args.perplexity, random_state=args.random_state, verbose=1)
    coords = tsne.fit_transform(embeddings_sample)
    print("t-SNE done.")

    if use_subset:
        result_df = pd.DataFrame({"x_coord": coords[:, 0], "y_coord": coords[:, 1]})
        if args.deep_labels and args.deep_labels.is_file():
            deep = np.load(args.deep_labels)
            result_df["deep_cluster"] = deep[indices]
        if args.wide_labels and args.wide_labels.is_file():
            wide = np.load(args.wide_labels)
            result_df["wide_cluster"] = wide[indices]
        # Если есть метаданные, берём их тоже по индексам
        if args.input_metadata and args.input_metadata.is_file():
            with open(args.input_metadata, "rb") as f:
                df_meta = pickle.load(f)
            result_df = pd.concat([df_meta.iloc[indices].reset_index(drop=True), result_df], axis=1)
    else:
        result_df = pd.DataFrame({"x_coord": coords[:, 0], "y_coord": coords[:, 1]})
        if args.deep_labels and args.deep_labels.is_file():
            result_df["deep_cluster"] = np.load(args.deep_labels)
        if args.wide_labels and args.wide_labels.is_file():
            result_df["wide_cluster"] = np.load(args.wide_labels)
        if args.input_metadata and args.input_metadata.is_file():
            with open(args.input_metadata, "rb") as f:
                df_meta = pickle.load(f)
            result_df = pd.concat([df_meta.reset_index(drop=True), result_df], axis=1)

    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    result_df.to_csv(args.output_csv, index=False)
    print(f"Saved to {args.output_csv}")

if __name__ == "__main__":
    main()