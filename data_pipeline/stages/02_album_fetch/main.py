from fetchers import *
from pipeman import DataPipelineContext
from pathlib import Path
import pandas as pd
import ast
from data_db import AlbumCoverDB
import requests
import time

def fetch_and_save_album_cover(db: AlbumCoverDB, album_index: int, album_row: pd.Series, total_albums: int, fetcher: GeniusFetcher, output_dir: Path) -> None:
    """
    Fetches and saves the album cover for a given album row.
    
    Args:
        db: Database instance for storing album covers.
        album_index: Index of the current album in the processing list.
        album_row: Pandas Series containing album data.
        total_albums: Total number of albums to process.
        fetcher: Fetcher instance for retrieving covers.
        output_dir: Directory to save the cover images.
    """
    album_id = album_row["album_id"]
    if db.get(album_id) is not None or not db.failed_to_load(album_id):
        album_name = album_row["album"]
        artist = ast.literal_eval(album_row["artists"])[0]
        print(f"Skipping: {artist} - {album_name}")
        return
    
    album_name = album_row["album"]
    artist = ast.literal_eval(album_row["artists"])[0]

    try:
        print(f"#{album_index + 1}/{total_albums}) \tProcessing {artist} - {album_name}")
        
        cover = fetcher.find_cover(artist, album_name, album_id=album_row["album_id"])
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 429:
            print(f"#{album_index + 1}/{total_albums}) \tRetrying {artist} - {album_name}")
            time.sleep(180)  # Wait 3 minutes before retrying
            fetch_and_save_album_cover(db, album_index, album_row, total_albums, fetcher, output_dir)
            return
        db.save_failed(AlbumCover(
            album_id=album_id,
            album_name=album_row["album"],
            artists=ast.literal_eval(album_row["artists"]),
            image_path=None,
            image=None,
            image_source=None,
            additional_info={}
        ))
        print(f"Error processing {artist} - {album_name}: {e}")
        return
    except Exception as e:
        db.save_failed(AlbumCover(
            album_id=album_id,
            album_name=album_row["album"],
            artists=ast.literal_eval(album_row["artists"]),
            image_path=None,
            image=None,
            image_source=None,
            additional_info={}
        ))
        print(f"Error processing {artist} - {album_name}: {e}")
        return
    
    print('Saving:', cover)
    db.save(cover)
    output_path = output_dir / f"{cover.album_id}.jpg"
    cover.image.convert('RGB').save(output_path)
    print('Saved to:', output_path)

def main(cxt: DataPipelineContext) -> None:
    """
    Main function to fetch album cover images from the input CSV file.
    
    Args:
        cxt: Data pipeline context providing file paths and configuration.
    """
    output_dir = cxt.get_file_path(cxt.get('ouput_folder_name'))
    print('Output folder:', output_dir)
    output_dir.mkdir(exist_ok=True)

    db = AlbumCoverDB(cxt.get_file_path('album_covers.db'))

    df = pd.read_csv(cxt.get_previous_stage_output_file_path())
    df = df.sample(frac=1).reset_index(drop=True)  # Shuffle the dataframe

    force_artist_search = False  # Flag to force artist search in fetcher
    subset = None
    if force_artist_search:
        subset = ["artists"]

    albums_to_process = df[["album_id", "album", "artists", "artist_ids"]].drop_duplicates(subset=subset).reset_index(drop=True)

    fetcher = GeniusFetcher(force_artist_search=force_artist_search)

    total_albums = len(albums_to_process)
    for album_index, album_row in albums_to_process.iterrows():
        fetch_and_save_album_cover(db, album_index, album_row, total_albums, fetcher, output_dir)

def desc() -> str:
    return "Fetch album cover images for the songs from input.csv file"