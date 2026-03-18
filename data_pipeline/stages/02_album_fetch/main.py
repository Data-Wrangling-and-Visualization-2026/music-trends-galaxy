from fetchers import *
from pipeman import DataPipelineContext
from pathlib import Path
import pandas as pd
import ast
from data_db import AlbumCoverDB

image_output_folder: Path = None

def main(cxt: DataPipelineContext) -> None:
    global image_output_folder
    image_output_folder = cxt.get_file_path(cxt.get('ouput_folder_name'))
    image_output_folder.mkdir(exist_ok=True) # Try to create foldere

    db = AlbumCoverDB(cxt.get_file_path('album_covers.db'))

    df = pd.read_csv(r'storage/tracks_features.csv')
    albums = df[["album_id", "album", "artists", "artist_ids"]].drop_duplicates().reset_index(drop=True)

    albums = albums[albums["artists"].map(lambda x: ast.literal_eval(x)[0]).isin(["Radiohhead", "Muse", "Metallica", "Bad Omens", "Architects", "Bring Me the Horizon", "Linkin Park"])]
    albums.reset_index(inplace=True, drop=True)

    f = GeniusFetcher()

    for i, r in albums.iterrows():
        print('\n'*2)
        try:
            album, artist = r["album"], ast.literal_eval(r["artists"])[0]
            print(f"#{i}) \tProcessing {artist} - {album}")
            
            s = f.find_cover(artist, album, album_id=r["album_id"])
        except Exception as e:
            db.save_failed(AlbumCover(
                album_id=r["album_id"],
                album_name=r["album"],
                artists=ast.literal_eval(r["artists"]),
                image_path=None,
                image=None,
                image_source=None,
                additional_info={}
            ))
            print(f"Error processing {artist} - {album}: {e}")
            continue
        
        print('Saving:', s)
        db.save(s)
        output = image_output_folder / f"{s.album_id}.jpg"

        s.image.convert('RGB').save(output)
        print('Saved to:', output)

        if i > 100:
            break

def desc() -> str:
    return "Fetch album information for the songs from input.csv file"