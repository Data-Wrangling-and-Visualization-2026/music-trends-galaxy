from pydantic import BaseModel, ConfigDict
from typing import List, Optional


class SongListItem(BaseModel):

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    artists: List[str]
    album: str
    album_id: str


class SongInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    artists: List[str]
    album: str
    album_id: str
    lyrics: str
    duration_ms: Optional[int] = None
    danceability: Optional[float] = None
    energy: Optional[float] = None
    valence: Optional[float] = None
    loudness: Optional[float] = None
    speechiness: Optional[float] = None
    acousticness: Optional[float] = None
    instrumentalness: Optional[float] = None
    liveness: Optional[float] = None
    tempo: Optional[float] = None
    year: Optional[int] = None


class GalaxyPoint(BaseModel):
    """One track for the 2D galaxy scatter (from embeded_data.csv)."""

    id: str
    name: str
    album: Optional[str] = None
    artists: Optional[str] = None
    x: float
    y: float
    lyrical_intensity: float
    lyrical_mood: float
    energy: float
    valence: float


class GalaxyPointsResponse(BaseModel):
    points: List[GalaxyPoint]
    count: int
    source_csv: str
    sample_mode: str


class GalaxyTrackListItem(BaseModel):
    """Track row from embeded_data.csv for home-page list (no lyrics)."""

    id: str
    name: str
    album: Optional[str] = None
    artists: Optional[str] = None
    x: float
    y: float


class GalaxyTracksResponse(BaseModel):
    tracks: List[GalaxyTrackListItem]
    count: int
    source_csv: str  # path or "sqlite" when from DB
