import sqlite3
import ast
import time
import requests
import pandas as pd
from pathlib import Path
from PIL import Image, ImageChops, ImageStat
from fetchers import GeniusFetcher
from pipeman import DataPipelineContext


def init_database(db_path: str) -> sqlite3.Connection:
    """Initializes the database and reserves ID=0 for references."""
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL;")
    cursor = conn.cursor()
    
    cursor.execute("CREATE TABLE IF NOT EXISTS images (id INTEGER PRIMARY KEY AUTOINCREMENT)")
    cursor.execute("CREATE TABLE IF NOT EXISTS artists (id TEXT PRIMARY KEY, image_id INTEGER NOT NULL DEFAULT 0)")
    cursor.execute("CREATE TABLE IF NOT EXISTS albums (id TEXT PRIMARY KEY, image_id INTEGER NOT NULL DEFAULT 0)")
    
    # Reserve 0 so AUTOINCREMENT starts from 1
    cursor.execute("INSERT OR IGNORE INTO images (id) VALUES (0)")
    conn.commit()
    return conn


def load_references(ref_paths: list[Path], compare_size: tuple = (64, 64)) -> list[Image.Image]:
    """Loads and transforms reference images into memory."""
    refs = []
    for p in ref_paths:
        if p.exists():
            img = Image.open(p).convert("RGB").resize(compare_size, Image.LANCZOS).convert("L")
            refs.append(img)
        else:
            print(f"Reference not found: {p}")
    if not refs:
        raise FileNotFoundError("No reference images found!")
    return refs


def calculate_similarity(img1_gray: Image.Image, img2_gray: Image.Image) -> float:
    """Returns normalized RMS difference: 0.0 (identical) -> 1.0 (different)."""
    diff = ImageChops.difference(img1_gray, img2_gray)
    stat = ImageStat.Stat(diff)
    return stat.rms[0] / 255.0


def fetch_and_save_album_cover(
    db: sqlite3.Connection,
    album_index: int,
    album_row: pd.Series,
    total_albums: int,
    fetcher: GeniusFetcher,
    output_dir: Path,
    references: list[Image.Image],
    target_size: tuple = (256, 256),
    similarity_threshold: float = 0.15
) -> None:
    album_id = str(album_row["album_id"])
    cursor = db.cursor()

    # Check if this ID has already been processed in any table
    cursor.execute(
        "SELECT id FROM artists WHERE id = ? UNION SELECT id FROM albums WHERE id = ?", 
        (album_id, album_id)
    )
    if cursor.fetchone() is not None:
        artist = ast.literal_eval(album_row["artists"])[0]
        print(f"Skipping: {artist} - {album_row['album']}")
        return

    artist = ast.literal_eval(album_row["artists"])[0]
    album_name = album_row["album"]

    try:
        print(f"#{album_index + 1}/{total_albums}) \tProcessing {artist} - {album_name}")
        cover = fetcher.find_cover(artist, album_name, album_id=album_id)
        
        if cover is None or cover.image is None:
            print(f"Cover not found for {artist} - {album_name}")
            return

        # 1. Prepare image in memory (no temporary files)
        img_rgb = cover.image.convert("RGB")
        img_compare = img_rgb.resize((64, 64), Image.LANCZOS).convert("L")

        # 2. Compare with both references
        is_similar = False
        for ref in references:
            if calculate_similarity(img_compare, ref) <= similarity_threshold:
                is_similar = True
                break

        if is_similar:
            image_id = 0
        else:
            cursor.execute("INSERT INTO images DEFAULT VALUES")
            image_id = cursor.lastrowid
            # Save only unique images
            dest_path = output_dir / f"{image_id}.jpg"
            img_rgb.resize(target_size, Image.LANCZOS).save(dest_path, "JPEG", optimize=True)

        # 3. Determine table based on found_class
        table_name = "artists" if str(getattr(cover, "found_class", "")).lower().startswith("artist") else "albums"

        # 4. Write to the appropriate table
        cursor.execute(
            f"INSERT OR REPLACE INTO {table_name} (id, image_id) VALUES (?, ?)",
            (album_id, image_id)
        )
        db.commit()
        print(f"{table_name.capitalize()} id={album_id} -> image_id={image_id}")

    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 429:
            print(f"⏳ Rate limit hit. Retrying {artist} - {album_name} in 180s...")
            time.sleep(180)
            fetch_and_save_album_cover(db, album_index, album_row, total_albums, fetcher, output_dir, references, target_size, similarity_threshold)
            return
        print(f"HTTP Error processing {artist} - {album_name}: {e}")
    except Exception as e:
        print(f"Error processing {artist} - {album_name}: {e}")


def main(cxt: DataPipelineContext) -> None:
    # Support corrected key name + fallback to typo from original
    output_folder_key = cxt.get('output_folder_name') or cxt.get('ouput_folder_name')
    output_dir = cxt.get_file_path(output_folder_key)
    print('Output folder:', output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    db_path = cxt.get_file_path('album_covers.db')
    db = init_database(db_path)

    # Load two references (paths can be taken from config or specified explicitly)
    ref_paths = [
        cxt.get('reference_artist.jpg'),
        cxt.get('reference_album.jpg')
    ]
    ref_paths = map(lambda x: Path(x).resolve().absolute(), ref_paths)
    ref_paths = list(ref_paths)
    references = load_references(ref_paths, compare_size=(64, 64))

    df = pd.read_csv(cxt.get_previous_stage_output_file_path())
    df = df.sample(frac=1).reset_index(drop=True)  # Shuffle

    force_artist_search = False
    subset = ["artists"] if force_artist_search else None
    albums_to_process = df[["album_id", "album", "artists", "artist_ids"]].drop_duplicates(subset=subset).reset_index(drop=True)

    fetcher = GeniusFetcher(force_artist_search=force_artist_search)
    total_albums = len(albums_to_process)

    for album_index, album_row in albums_to_process.iterrows():
        fetch_and_save_album_cover(
            db=db,
            album_index=album_index,
            album_row=album_row,
            total_albums=total_albums,
            fetcher=fetcher,
            output_dir=output_dir,
            references=references,
            target_size=(256, 256),
            similarity_threshold=0.15
        )

    db.close()
    print("Processing completed.")


def desc() -> str:
    return "Fetch album covers, deduplicate against two references, and store in normalized artists/albums/images DB."