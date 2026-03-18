"""
Lyrics enrichment pipeline for track metadata using LRCLib.

This module provides batch processing of a tracks CSV: for each row it looks up
lyrics via the LRCLib API (via LRCLibParser), then appends the result columns
(lyrics_status, lyrics_plain, lyrics_synced, etc.) and writes an enriched CSV.
It supports chunked reading, resumability (skip already-processed rows by id),
optional row limits, and configurable throttling (sleep between requests).
Can be run as a script (see __main__) or used programmatically via
add_tracks_csv().
"""
from __future__ import annotations

from libsrc_api import LRCLibParser
from concurrent.futures import ThreadPoolExecutor, as_completed
import ast
import time
from pathlib import Path
from typing import Any, Dict, Optional
import pandas as pd
from types import LyricsRecordLibSRC

# -----------------------------------------------------------------------------
# Default paths when run as script (relative to this file's directory)
# -----------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
INPUT_CSV = BASE_DIR / "tracks_features.csv"
OUTPUT_CSV = BASE_DIR / "tracks_features_with_lyrics.csv"


def parse_first_artist(artists_value: Any) -> str:
    """
    Extract the first artist name from a value that may be a list or list-like string.

    CSV/DataFrame "artists" columns are sometimes stored as:
    - A Python list (e.g. from previous processing)
    - A string representation of a list (e.g. "['Artist A', 'Artist B']")
    - A single string (e.g. "Artist A")
    - None or "nan"

    Returns the first artist as a stripped string, or "" if none can be derived.
    """
    if artists_value is None:
        return ""

    # Already a list (e.g. from DataFrame): take first element
    if isinstance(artists_value, list):
        return str(artists_value[0]).strip() if artists_value else ""

    text = str(artists_value).strip()
    if not text or text.lower() == "nan":
        return ""

    # Try to parse string as a literal list (e.g. "['A', 'B']") and take first
    try:
        parsed = ast.literal_eval(text)
        if isinstance(parsed, list) and parsed:
            return str(parsed[0]).strip()
    except Exception:
        pass

    # Treat the whole string as a single artist name
    return text


def row_to_query(row: pd.Series) -> Dict[str, Optional[Any]]:
    """
    Build a lyrics lookup query dict from a single DataFrame row (track metadata).

    Expects columns: name, album, artists, duration_ms.
    - track_name: from "name", stripped (required for lookup).
    - artist_name: first artist from "artists" via parse_first_artist().
    - album_name: from "album", stripped; None if missing/empty.
    - duration: from "duration_ms" converted to seconds (float, 3 decimals), or None.

    Returns a dict suitable for passing to LRCLibParser.get_lyrics() (or equivalent).
    """
    track_name = str(row.get("name", "") or "").strip()
    album_name = str(row.get("album", "") or "").strip() or None
    artist_name = parse_first_artist(row.get("artists"))

    # Convert milliseconds to seconds for API matching; ignore invalid values
    duration = None
    duration_ms = row.get("duration_ms")
    if pd.notna(duration_ms):
        try:
            duration = round(float(duration_ms) / 1000.0, 3)
        except Exception:
            duration = None

    return {
        "track_name": track_name,
        "artist_name": artist_name,
        "album_name": album_name,
        "duration": duration,
    }

def empty_result() -> Dict[str, Any]:
    """
    Return the canonical "no lyrics" result structure for one track.

    All lyrics-related fields are None; lyrics_status is "not_found" and
    lyrics_source is "lrclib". This shape is merged into each row so the
    output CSV has consistent columns whether or not lyrics were found.
    """
    return {
        "lyrics_status": "not_found",
        "lyrics_source": "lrclib",
        "lyrics_id": None,
        "matched_track_name": None,
        "matched_artist_name": None,
        "matched_album_name": None,
        "matched_duration": None,
        "lyrics_instrumental": None,
        "lyrics_plain": None,
        "lyrics_synced": None,
    }


def record_to_result(record: LyricsRecordLibSRC) -> Dict[str, Any]:
    """
    Convert a successful LRCLib record into the same dict shape as empty_result().

    Fills in lyrics_status="ok" and all matched/lyrics fields from the record.
    Used so every row gets the same set of columns in the output CSV.
    """
    return {
        "lyrics_status": "ok",
        "lyrics_source": "lrclib",
        "lyrics_id": record.id,
        "matched_track_name": record.track_name,
        "matched_artist_name": record.artist_name,
        "matched_album_name": record.album_name,
        "matched_duration": record.duration,
        "lyrics_instrumental": record.instrumental,
        "lyrics_plain": record.plain_lyrics,
        "lyrics_synced": record.synced_lyrics,
    }

def find_track(parser: LRCLibParser, row: pd.Series) -> Dict[str, Any]:
    """
    Look up lyrics for a single track row and return an enrichment result dict.

    Uses row_to_query() to build the API query. If track_name or artist_name
    is missing, returns result with lyrics_status="bad_input" and no API call.
    On success, returns record_to_result(record); on any exception, returns
    result with lyrics_status="error: <ExceptionType>". The returned dict
    always has the same keys as empty_result() for consistent CSV columns.
    """
    query = row_to_query(row)
    result = empty_result()

    if not query["track_name"] or not query["artist_name"]:
        result["lyrics_status"] = "bad_input"
        return result

    try:
        record = parser.get_lyrics(
            track_name=query["track_name"],
            artist_name=query["artist_name"],
            album_name=query["album_name"],
            duration=query["duration"],
        )
        return record_to_result(record)
    except Exception as exc:
        result["lyrics_status"] = f"error: {type(exc).__name__}"
        return result


def add_tracks_csv(
    input_csv: Path,
    output_csv: Path,
    *,
    chunksize: int,
    max_rows: Optional[int],
    sleep_sec: float,
    start_row: int
) -> None:
    """
    Read a tracks CSV in chunks, enrich each row with lyrics from LRCLib, append to output CSV.

    Parameters
    ----------
    input_csv : Path
        Path to the input CSV with track metadata (expected columns: id, name, album, artists, duration_ms).
    output_csv : Path
        Path where enriched rows are appended (same columns plus lyrics_* and matched_*).
    chunksize : int
        Number of rows to read from the input CSV per chunk.
    max_rows : Optional[int]
        If set, stop after processing this many rows in total (across all chunks).
    sleep_sec : float
        Seconds to sleep after each track lookup (throttling to avoid rate limits).
    start_row : int
        Number of rows to skip at the start of the input (1-based: skip rows 1..start_row).

    Behavior
    --------
    - Resumable: if output_csv already exists, each chunk loads existing output "id" column
      and skips rows whose id is already present, so re-runs do not duplicate work.
    - Chunked I/O: input is read with pandas in chunks; each chunk is processed with a
      ThreadPoolExecutor (10 workers), then appended to output_csv (header only on first write).
    - Progress and timing are printed per chunk and at the end.
    """
    # Count how many rows in the existing output already have lyrics_status == "ok" (for reporting)
    overall_succes_processed = 0
    if output_csv.exists():
        try:
            existing = pd.read_csv(output_csv, usecols=['lyrics_status'])
            overall_succes_processed += (existing['lyrics_status'] == 'ok').sum()
        except Exception:
            output_csv.unlink()

    start_total_time = time.perf_counter()
    parser = LRCLibParser()
    output_csv.parent.mkdir(parents=True, exist_ok=True)

    rows_processed = 0
    write_header = True

    # Skip the first start_row rows of the input (skiprows is 0-based row indices to skip)
    skip_rows = range(1, start_row + 1) if start_row > 0 else None
    chunk_iter = pd.read_csv(input_csv, chunksize=chunksize, skiprows=skip_rows)

    for chunk_index, chunk in enumerate(chunk_iter, start=1):
        already_processed_track_counter = 0
        with_ok_status_track_counter = 0
        with_error_track_counter = 0

        start_local_time = time.perf_counter()

        # Load set of track ids already present in output (for resumability)
        processed_ids = set()
        if output_csv.exists():
            try:
                existing_ids = pd.read_csv(output_csv, usecols=['id'])
                processed_ids = set(existing_ids['id'].astype(str))
            except Exception:
                output_csv.unlink()

        if max_rows is not None and rows_processed >= max_rows:
            break

        # Cap this chunk to remaining allowed rows if max_rows is set
        if max_rows is not None:
            remaining = max_rows - rows_processed
            if remaining <= 0:
                break
            if len(chunk) > remaining:
                chunk = chunk.iloc[:remaining].copy()

        # Drop rows that were already processed (by id) so we only call the API for new ones
        if processed_ids:
            chunk_ids = chunk['id'].astype(str)
            mask = ~chunk_ids.isin(processed_ids)
            new_chunk = chunk[mask].copy()
            already_processed_track_counter = chunksize - len(new_chunk)
            rows_processed += already_processed_track_counter
        else:
            new_chunk = chunk.copy()

        enriched_rows = []

        # Run find_track for each row in this chunk in parallel (up to 10 workers)
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = {
                executor.submit(find_track, parser, row): row
                for _, row in new_chunk.iterrows()
            }

            for future in as_completed(futures):
                row = futures[future]
                try:
                    enrich_data = future.result()
                    if enrich_data["lyrics_status"] == "ok":
                        with_ok_status_track_counter += 1
                    else:
                        with_error_track_counter += 1
                except Exception as e:
                    enrich_data = {"lyrics_status": f"error: {type(e).__name__}"}

                row_dict = row.to_dict()
                row_dict.update(enrich_data)
                enriched_rows.append(row_dict)
                rows_processed += 1
                if sleep_sec > 0:
                    time.sleep(sleep_sec)

        out_chunk = pd.DataFrame(enriched_rows)
        out_chunk.to_csv(output_csv, mode="a", index=False, header=write_header)
        write_header = False
        end_local_time = time.perf_counter()
        overall_succes_processed += with_ok_status_track_counter

        print(f"Chunk={chunk_index} processed={rows_processed} output={output_csv}")
        print(f"Time for {chunksize} chunks: {end_local_time - start_local_time:.2f}s, Total time: {end_local_time - start_total_time:.2f}s")
        print(f"Found before: {already_processed_track_counter}, processed with ok status: {with_ok_status_track_counter}, processed with error: {with_error_track_counter}")
        print(f"Overall success number: {overall_succes_processed}. Overall success rate: {overall_succes_processed/rows_processed}")

    print(f"Done. Total rows processed: {rows_processed}")
    print(f"Saved to: {output_csv}")


if __name__ == "__main__":
    # Run the lyrics enrichment pipeline with default paths and parameters.
    # - Reads from tracks_features.csv in this directory, writes to tracks_features_with_lyrics.csv.
    # - Processes 1000 rows per chunk; no max_rows limit; 0.05s sleep between lookups to throttle API.
    add_tracks_csv(
        input_csv=INPUT_CSV,
        output_csv=OUTPUT_CSV,
        chunksize=1000,
        max_rows=None,
        sleep_sec=0.05,
        start_row=0
    )