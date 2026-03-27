from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class PerMetricStats(BaseModel):
    """One metric from pipeline: min / max / mean of many tracks."""

    model_config = ConfigDict(extra="ignore")

    min: Optional[float] = None
    max: Optional[float] = None
    mean: Optional[float] = None


class MetricStatsBlock(BaseModel):
    """
    Block of metrics for cluster / artist / album.
    Matches the keys in METRIC_COLUMNS in data_pipeline.
    """

    model_config = ConfigDict(extra="ignore")

    lyrical_intensity: Optional[PerMetricStats] = None
    lyrical_mood: Optional[PerMetricStats] = None
    energy: Optional[PerMetricStats] = None
    valence: Optional[PerMetricStats] = None


class ClusterLlmInfo(BaseModel):
    code: str = Field(..., description="Cluster code (as in embeded_data / dim_clusters).")
    name: Optional[str] = Field(None, description="Short label (from LLM / dim_clusters.name).")
    description: Optional[str] = Field(None, description="LLM prose (dim_clusters.description).")
    track_count: Optional[int] = Field(None, description="Tracks in cluster (dim_clusters.track_count).")
    metrics: Optional[MetricStatsBlock] = Field(None, description="min/max/mean (dim_clusters.metrics_json).")
    color: Optional[str] = Field(None, description="Optional UI color (dim_clusters.color).")


class ArtistLlmInfo(BaseModel):
    id: str = Field(..., description="Spotify artist id (dim_artists.id).")
    name: str = Field(..., description="Display name.")
    track_count: Optional[int] = Field(None, description="dim_artists.track_count.")
    metrics: Optional[MetricStatsBlock] = Field(None, description="dim_artists.metrics_json.")
    color: Optional[str] = Field(None, description="Optional UI color (dim_artists.color).")
    updated_at: Optional[datetime] = Field(None, description="dim_artists.updated_at.")
    cover_image_id: Optional[int] = Field(
        None,
        description="Dedup image id from pipeline DB; file at storage/images/images/{id}.jpg.",
    )


class AlbumLlmInfo(BaseModel):
    id: str = Field(..., description="Album id (dim_albums.id).")
    title: Optional[str] = Field(None, description="Album title.")
    track_count: Optional[int] = Field(None, description="dim_albums.track_count.")
    metrics: Optional[MetricStatsBlock] = Field(None, description="dim_albums.metrics_json.")
    color: Optional[str] = Field(None, description="Optional UI color (dim_albums.color).")
    updated_at: Optional[datetime] = Field(None, description="dim_albums.updated_at.")
    cover_image_id: Optional[int] = Field(
        None,
        description="Dedup image id from pipeline DB; file at storage/images/images/{id}.jpg.",
    )


class SongListItem(BaseModel):
    """One row in the song list."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="Internal song id.")
    name: str = Field(..., description="Song name.")
    artists: List[str] = Field(..., description="List of artist names.")
    album: str = Field(..., description="Album.")
    album_id: str = Field(..., description="Album id.")


class SongInfo(BaseModel):
    """Song with text."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="Internal song id.")
    name: str = Field(..., description="Song name.")
    artists: List[str] = Field(..., description="List of artist names.")
    album: str = Field(..., description="Album.")
    album_id: str = Field(..., description="Album id.")
    lyrics: str = Field(..., description="Full text.")


class SongFullInfo(BaseModel):
    """Extended model with audio features."""

    id: int = Field(..., description="Internal song id.")
    name: str = Field(..., description="Song name.")
    artists: List[str] = Field(..., description="List of artist names.")
    album: str = Field(..., description="Album.")
    album_id: Optional[str] = Field(None, description="Album id.")
    lyrics: Optional[str] = Field(None, description="Text.")
    duration_ms: Optional[int] = Field(None, description="Duration, ms.")
    danceability: Optional[float] = Field(None, description="Danceability 0–1.")
    energy: Optional[float] = Field(None, description="Energy 0–1.")
    valence: Optional[float] = Field(None, description="Valence 0–1.")
    loudness: Optional[float] = Field(None, description="Loudness, dB.")
    speechiness: Optional[float] = Field(None, description="Speechiness 0–1.")
    acousticness: Optional[float] = Field(None, description="Acousticness 0–1.")
    instrumentalness: Optional[float] = Field(None, description="Instrumentalness 0–1.")
    liveness: Optional[float] = Field(None, description="Liveness 0–1.")
    tempo: Optional[float] = Field(None, description="BPM.")
    year: Optional[int] = Field(None, description="Release year.")


class GalaxyPoint(BaseModel):
    """Point on the map: coordinates and scores for visualization."""

    id: str = Field(..., description="track_id == preprocessed_tracks.id.")
    name: str = Field(..., description="Track name.")
    album: Optional[str] = Field(None, description="Album.")
    artists: Optional[str] = Field(None, description="Field artists as in CSV.")
    x: float = Field(..., description="X (projection).")
    y: float = Field(..., description="Y (projection).")
    z: float = Field(0.0, description="Z (default 0).")
    lyrical_intensity: float = Field(..., description="Lyrical intensity (often 0–1).")
    lyrical_mood: float = Field(..., description="Lyrical mood.")
    energy: float = Field(..., description="Energy for coloring.")
    valence: float = Field(..., description="Valence for coloring.")
    audio_features: Optional[Dict[str, Any]] = Field(
        None,
        description="Spotify-style metrics from fact_track_audio_features (same keys as /api/tracks/:id).",
    )
    cluster_code: Optional[str] = None
    cluster: Optional[ClusterLlmInfo] = None


class GalaxyPointsResponse(BaseModel):
    points: List[GalaxyPoint] = Field(..., description="Points in this response.")
    count: int = Field(..., description="Number of points.")
    source_csv: str = Field(..., description="Source / tag.")
    sample_mode: str = Field(..., description="first | random.")


class GalaxyTrackListItem(BaseModel):
    """Row in the track list (without lyrics)."""

    id: str = Field(..., description="Track id.")
    name: str = Field(..., description="Track name.")
    album: Optional[str] = None
    album_id: Optional[str] = Field(None, description="From preprocessed_tracks.")
    artists: Optional[str] = None
    artist_ids: Optional[str] = Field(
        None,
        description="JSON array string as stored in preprocessed_tracks (for filter UI).",
    )
    year: Optional[int] = Field(None, description="Release year when known.")
    x: float = Field(..., description="Galaxy X.")
    y: float = Field(..., description="Galaxy Y.")
    z: float = Field(0.0, description="Galaxy Z.")
    cluster_code: Optional[str] = None
    cluster: Optional[ClusterLlmInfo] = None


class DimArtistBrief(BaseModel):
    id: str
    name: str
    track_count: Optional[int] = None
    color: Optional[str] = None
    cover_image_id: Optional[int] = None
    metrics_json: Optional[Dict[str, Any]] = None
    genres: List[str] = Field(
        default_factory=list,
        description="Tag strings from dim_artists.metrics_json.genres when present.",
    )


class DimAlbumBrief(BaseModel):
    id: str
    title: str
    track_count: Optional[int] = None
    color: Optional[str] = None
    cover_image_id: Optional[int] = None
    metrics_json: Optional[Dict[str, Any]] = None
    genres: List[str] = Field(
        default_factory=list,
        description="Tag strings from dim_albums.metrics_json.genres when present.",
    )


class GalaxyTracksResponse(BaseModel):
    tracks: List[GalaxyTrackListItem] = Field(..., description="Tracks for the list.")
    count: int = Field(..., description="Number of rows.")
    source_csv: str = Field(..., description="Source tag.")
    sample_mode: str = Field(..., description="first | random (same semantics as /points).")


class DimClusterRow(BaseModel):
    """One row from ``dim_clusters`` (filters, genre list, map cluster colors)."""

    model_config = ConfigDict(from_attributes=True)

    code: str
    name: Optional[str] = None
    track_count: Optional[int] = None
    description: Optional[str] = None
    color: Optional[str] = None
    metrics_json: Optional[Dict[str, Any]] = None


class ClustersListResponse(BaseModel):
    clusters: List[DimClusterRow]
    count: int