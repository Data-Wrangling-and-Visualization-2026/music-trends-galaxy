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
    matched_name: str
    matched_album: str | None
    matched_artist: str
    lyrics: str | None
    lyrics_instrumental: bool | None
    lyrics_source: str
    raw_response: Dict[str, Any]
