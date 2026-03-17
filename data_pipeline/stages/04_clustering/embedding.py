"""
Stage 1: Generate embeddings for song lyrics.

Uses sentence-transformers. Input: CSV with 'lyrics' column (configurable).
Output: .npy embeddings and optional .pkl metadata DataFrame.
"""

import argparse
import sys
import pickle
from pathlib import Path

import numpy as np
import pandas as pd
from sentence_transformers import SentenceTransformer
from tqdm import tqdm


def main():
    parser = argparse.ArgumentParser(description="Generate embeddings for songs")
    parser.add_argument("input", type=Path, help="Input CSV path")
    parser.add_argument("output_embeddings", type=Path, help="Output .npy embeddings path")
    parser.add_argument("--output-metadata", type=Path, default=None,
                        help="Output .pkl metadata path (optional)")
    parser.add_argument("--text-column", default="lyrics", help="Text column name")
    parser.add_argument("--model", default="all-MiniLM-L6-v2", help="Embedding model")
    parser.add_argument("--batch-size", type=int, default=32, help="Batch size")
    parser.add_argument("--limit", type=int, default=None, help="Max rows to process")
    args = parser.parse_args()

    if not args.input.is_file():
        print(f"Error: file not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    print(f"Loading data from {args.input}...")
    df = pd.read_csv(args.input)
    if args.limit:
        df = df.head(args.limit)

    if args.text_column not in df.columns:
        print(f"Column '{args.text_column}' not found. Available: {list(df.columns)}", file=sys.stderr)
        sys.exit(1)

    texts = df[args.text_column].fillna("").astype(str).tolist()
    print(f"Total rows: {len(texts)}")

    print(f"Loading model {args.model}...")
    model = SentenceTransformer(args.model)

    print("Generating embeddings...")
    embeddings = []
    for i in tqdm(range(0, len(texts), args.batch_size)):
        batch = texts[i:i+args.batch_size]
        emb = model.encode(batch, show_progress_bar=False)
        embeddings.append(emb)
    embeddings = np.vstack(embeddings)
    print(f"Embeddings shape: {embeddings.shape}")

    args.output_embeddings.parent.mkdir(parents=True, exist_ok=True)
    np.save(args.output_embeddings, embeddings)
    print(f"Embeddings saved to {args.output_embeddings}")

    if args.output_metadata:
        args.output_metadata.parent.mkdir(parents=True, exist_ok=True)
        with open(args.output_metadata, "wb") as f:
            pickle.dump(df, f)
        print(f"Metadata saved to {args.output_metadata}")

if __name__ == "__main__":
    main()