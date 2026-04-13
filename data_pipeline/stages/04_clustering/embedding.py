"""
Stage 1: Generate embeddings for song lyrics (+ optional Spotify audio feature concat).

Uses sentence-transformers. Default model: nomic-ai/nomic-embed-text-v1.5 (long context, trust_remote_code).
Input: CSV with 'lyrics' column (configurable) and optional audio columns.
Output: .npy embeddings and optional .pkl metadata DataFrame.
"""

import argparse
import inspect
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.preprocessing import normalize
from sentence_transformers import SentenceTransformer
from tqdm import tqdm

from audio_fusion import maybe_fused_audio

DEFAULT_MODEL = "nomic-ai/nomic-embed-text-v1.5"


def load_sentence_model(model_id: str) -> SentenceTransformer:
    """Nomic (and some HF models) require trust_remote_code."""
    kwargs = {}
    if "nomic" in model_id.lower():
        kwargs["trust_remote_code"] = True
    return SentenceTransformer(model_id, **kwargs)


def encode_batches(model: SentenceTransformer, texts: list[str], batch_size: int) -> np.ndarray:
    """Encode with Nomic 'document' prompt when the model supports it."""
    sig = inspect.signature(model.encode)
    use_prompt = "prompt_name" in sig.parameters
    embeddings = []
    for i in tqdm(range(0, len(texts), batch_size)):
        batch = texts[i : i + batch_size]
        if use_prompt:
            emb = model.encode(batch, show_progress_bar=False, prompt_name="document")
        else:
            emb = model.encode(batch, show_progress_bar=False)
        embeddings.append(emb)
    return np.vstack(embeddings)


def main():
    parser = argparse.ArgumentParser(description="Generate embeddings for songs")
    parser.add_argument("input", type=Path, help="Input CSV path")
    parser.add_argument("output_embeddings", type=Path, help="Output .npy embeddings path")
    parser.add_argument("--output-metadata", type=Path, default=None,
                        help="Output .pkl metadata path (optional)")
    parser.add_argument("--text-column", default="lyrics", help="Text column name")
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help="sentence-transformers model id (default: Nomic embed text v1.5)",
    )
    parser.add_argument("--batch-size", type=int, default=16, help="Batch size")
    parser.add_argument("--limit", type=int, default=None, help="Max rows to process")
    parser.add_argument(
        "--no-fuse-audio",
        dest="fuse_audio",
        action="store_false",
        default=True,
        help="Disable concat of normalized Spotify audio columns after text embedding",
    )
    parser.add_argument(
        "--audio-fusion-scale",
        type=float,
        default=1.0,
        help="Extra weight on L2-normalized audio block (after per-row L2=1; default 1.0)",
    )
    parser.add_argument(
        "--no-l2-modality-norm",
        action="store_true",
        help="Skip L2 per modality (text row + audio row) before concat — not recommended",
    )
    args = parser.parse_args()

    if not args.input.is_file():
        print(f"Error: file not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    print(f"Loading data from {args.input}...", flush=True)
    df = pd.read_csv(args.input, nrows=args.limit if args.limit else None)
    if args.limit:
        print(f"Limited to {len(df)} rows.", flush=True)

    if args.text_column not in df.columns:
        print(f"Column '{args.text_column}' not found. Available: {list(df.columns)}", file=sys.stderr)
        sys.exit(1)

    texts = df[args.text_column].fillna("").astype(str).tolist()
    print(f"Total rows: {len(texts)}", flush=True)

    print(f"Loading model {args.model} (first run may download weights)...", flush=True)
    model = load_sentence_model(args.model)
    model.max_seq_length = 512
    print("Model loaded. Generating text embeddings...", flush=True)
    embeddings = encode_batches(model, texts, args.batch_size)
    print(f"Text embedding shape: {embeddings.shape}", flush=True)

    if args.no_l2_modality_norm:
        audio_part = maybe_fused_audio(
            df,
            fuse=args.fuse_audio,
            scale=args.audio_fusion_scale,
        )
    else:
        audio_part = maybe_fused_audio(df, fuse=args.fuse_audio, scale=1.0)

    if audio_part is not None:
        if audio_part.shape[0] != embeddings.shape[0]:
            print("Error: audio block row count mismatch.", file=sys.stderr)
            sys.exit(1)
        if args.no_l2_modality_norm:
            text_blk = embeddings.astype(np.float32)
            audio_blk = audio_part.astype(np.float32)
            print("Warning: --no-l2-modality-norm: concat without per-modality L2.", flush=True)
        else:
            text_blk = normalize(embeddings, norm="l2", axis=1).astype(np.float32)
            audio_blk = normalize(audio_part, norm="l2", axis=1).astype(np.float32)
            audio_blk *= np.float32(args.audio_fusion_scale)
            print(
                "L2-normalized text and audio rows (modality balance), optional --audio-fusion-scale on audio.",
                flush=True,
            )
        embeddings = np.hstack([text_blk, audio_blk]).astype(np.float32)
        print(f"Fused with audio block → shape: {embeddings.shape}", flush=True)
    else:
        if not args.no_l2_modality_norm:
            embeddings = normalize(embeddings, norm="l2", axis=1).astype(np.float32)
            print("L2-normalized text embeddings per row (text-only).", flush=True)

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
