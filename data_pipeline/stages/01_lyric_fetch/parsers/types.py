import dataclasses

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