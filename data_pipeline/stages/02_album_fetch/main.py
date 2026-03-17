from fetchers import *
from pipeman import DataPipelineContext
import pandas as pd
import ast
from cover_bd import AlbumCoverDB

import os

folder = 'folder'

# os.mkdir(folder)

def main(cxt: DataPipelineContext) -> None:
    db = AlbumCoverDB("db.db")

    df = pd.read_csv(r'storage/tracks_features.csv')
    albums = df[["album_id", "album", "artists", "artist_ids"]].drop_duplicates().reset_index(drop=True)

    albums = albums[albums["artists"].map(lambda x: ast.literal_eval(x)[0]).isin(["Radiohhead", "Muse", "Metallica", "Bad Omens", "Architects", "Bring Me the Horizon", "Linkin Park"])]
    albums.reset_index(inplace=True, drop=True)

    f = GeniusFetcher()

    for i, r in albums.iterrows():
        try:
            album, artist = r["album"], ast.literal_eval(r["artists"])[0]
            print(f"#{i}) \tProcessing {artist} - {album}")
            
            s = f.find_cover(artist, album)
        except Exception as e:
            print(f"Error processing {artist} - {album}: {e}")
            continue

        db.insert_or_replace(s)
        s.image.save(f"{folder}/{s.album_id}.jpg")

        if i > 100:
            break

def desc() -> str:
    return "Fetch album information for the songs from input.csv file"