import dataclasses
from typing import Optional, Dict, Any

## Types
@dataclasses.dataclass
class SongEntry:
    name: str
    artis: str
    path: str
    src: str

@dataclasses.dataclass
class LyricEntry:
    name: str
    artist: str
    lyrics: str
    src: str

@dataclasses.dataclass
class LyricsRecordLibSRC:
    id: Optional[int]
    track_name: str
    artist_name: str
    album_name: Optional[str]
    duration: Optional[float]
    instrumental: bool
    plain_lyrics: Optional[str]
    synced_lyrics: Optional[str]
    raw: Dict[str, Any]