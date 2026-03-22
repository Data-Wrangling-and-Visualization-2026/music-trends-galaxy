from pipeman import DataPipelineContext
from pathlib import Path
import pandas as pd
import ast

def remove_instrumental(df: pd.DataFrame) -> pd.DataFrame:
    # try to remove mostly instrumental songs
    # but some instrumental song still be present, 
    # because of the nature of the feature and some songs are actually instrumental but have some noise in them
    if 'instrumentalness' not in df.columns:
        return df.copy()
    # coerce to numeric, drop rows that can't be parsed
    instrumental = pd.to_numeric(df['instrumentalness'], errors='coerce')
    valid_idx = instrumental.notna()
    if not valid_idx.all():
        df = df.loc[valid_idx].copy()
        instrumental = instrumental[valid_idx]
    return df.loc[instrumental <= 0.95].copy()

def remove_live_songs(df: pd.DataFrame) -> pd.DataFrame:
    # Remove songs that are live performances 
    # (If they have "live at" in their name)
    return df[~df['name'].str.lower().str.contains("live at")]

def remove_copies(df: pd.DataFrame) -> pd.DataFrame:
    # Some songs are present in multiuple albums
    # e.g. live, singles that are presented before album release, some collections, etc.
    # We want to keep only one copy of the song, and we will prefer albums with more songs in them,
    # because they are more likely to be the main album of the song, rather than some single or collection.

    # Work on a copy to avoid SettingWithCopyWarning
    df = df.copy()

    # Add a column for the number of songs in each album
    df['album_size'] = df.groupby('album_id')['album_id'].transform('size')

    # Sort the dataframe by 'artists', 'name', and 'album_size' in descending order
    df = df.sort_values(by=['artists', 'name', 'album_size'], ascending=[True, True, False])

    # Drop duplicates based on 'artists' and 'name', keeping the first occurrence (which has the largest album_size)
    df = df.drop_duplicates(subset=['artists', 'name'], keep='first')

    # Optionally, drop the 'album_size' column if not needed
    df = df.drop(columns=['album_size'])

    return df


def main(cxt: DataPipelineContext) -> None:
    input_path = cxt.get_previous_stage_output_file_path()

    df = pd.read_csv(input_path)

    initial_count = len(df)
    print(f"Initial number of songs: {initial_count}")

    df = df.drop(columns=['track_number', 'disc_number', 'explicit', 'year', 'release_date'], errors='ignore') # remove unused columns, ignore if they are not present
    df = df.dropna(subset=['name', 'artists', 'album_id'])
    df = df.drop_duplicates(subset=['name', 'artists', 'album_id'])
    df = remove_instrumental(df)
    df = remove_live_songs(df)
    df = remove_copies(df)
    
    final_count = len(df)
    print(f"Final number of songs after preprocessing: {final_count}")
    
    print(f"Removed {initial_count - final_count} songs during preprocessing.")
    
    output_path = cxt.get_output_file_path()
    df.to_csv(output_path, index=False)
    print(f"Preprocessed data saved to: {output_path}")

def desc() -> str:
    return "Preprocess the raw data and get rid of redundant rows in initial dataset"
