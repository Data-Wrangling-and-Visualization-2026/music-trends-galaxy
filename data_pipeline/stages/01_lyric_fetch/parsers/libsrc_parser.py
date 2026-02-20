from __future__ import annotations
from libsrc_api import LRCLibParser
from concurrent.futures import ThreadPoolExecutor, as_completed
import ast
import time
from pathlib import Path
from typing import Any, Dict, Optional
import pandas as pd
from types import LyricsRecordLibSRC

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
INPUT_CSV = BASE_DIR / "tracks_features.csv"
OUTPUT_CSV = BASE_DIR / "tracks_features_with_lyrics.csv"

def parse_first_artist(artists_value: Any) -> str:
    if artists_value is None:
        return ""

    if isinstance(artists_value, list):
        return str(artists_value[0]).strip() if artists_value else ""

    text = str(artists_value).strip()
    if not text or text.lower() == "nan":
        return ""

    try:
        parsed = ast.literal_eval(text)
        if isinstance(parsed, list) and parsed:
            return str(parsed[0]).strip()
    except Exception:
        pass

    return text

def row_to_query(row: pd.Series) -> Dict[str, Optional[Any]]:
    track_name = str(row.get("name", "") or "").strip()
    album_name = str(row.get("album", "") or "").strip() or None
    artist_name = parse_first_artist(row.get("artists"))

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
    overall_succes_processed = 0
    if output_csv.exists():
            try:
                existing = pd.read_csv(output_csv, usecols=['lyrics_status'])
                overall_succes_processed += (existing['lyrics_status'] == 'ok').sum()
            except Exception as e:
                output_csv.unlink()

    start_total_time = time.perf_counter()
    parser = LRCLibParser()
    output_csv.parent.mkdir(parents=True, exist_ok=True)

    rows_processed = 0
    write_header = True

    skip_rows = range(1, start_row + 1) if start_row > 0 else None
    chunk_iter = pd.read_csv(input_csv, chunksize=chunksize, skiprows=skip_rows)

    for chunk_index, chunk in enumerate(chunk_iter, start=1):
        already_processed_track_counter = 0
        with_ok_status_track_counter = 0
        with_error_track_counter = 0

        start_local_time = time.perf_counter()

        processed_ids = set()
        if output_csv.exists():
            try:
                existing_ids = pd.read_csv(output_csv, usecols=['id'])
                processed_ids = set(existing_ids['id'].astype(str))
            except Exception as e:
                output_csv.unlink()

        if max_rows is not None and rows_processed >= max_rows:
            break

        if max_rows is not None:
            remaining = max_rows - rows_processed
            if remaining <= 0:
                break
            if len(chunk) > remaining:
                chunk = chunk.iloc[:remaining].copy()

        if processed_ids:
            chunk_ids = chunk['id'].astype(str)
            mask = ~chunk_ids.isin(processed_ids)
            new_chunk = chunk[mask].copy()
            already_processed_track_counter = chunksize - len(new_chunk)
            rows_processed += already_processed_track_counter
        else:
            new_chunk = chunk.copy()

        enriched_rows = []


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
        print(f"Time for {chunksize} chuunks: {end_local_time - start_local_time:.2f}s, Total time: {end_local_time - start_total_time:.2f}s")
        print(f"Found before: {already_processed_track_counter}, processed with ok status: {with_ok_status_track_counter}, processed with error: {with_error_track_counter}")
        print(f"Overall success number: {overall_succes_processed}. Overall success rate: {overall_succes_processed/rows_processed}")

    print(f"Done. Total rows processed: {rows_processed}")
    print(f"Saved to: {output_csv}")


if __name__ == "__main__":
    add_tracks_csv(
        input_csv=INPUT_CSV,
        output_csv=OUTPUT_CSV,
        chunksize=1000,
        max_rows=None,
        sleep_sec=0.05,
        start_row=0
    )
