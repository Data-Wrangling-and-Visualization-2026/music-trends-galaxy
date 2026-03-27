
from sqlalchemy import (
    Boolean,
    Column,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    DateTime,
    func,
    JSON,
)
from sqlalchemy.orm import relationship

from .database import Base


# Canonical table: mirror of storage/preproccessed.csv
class PreprocessedTrack(Base):
    """
    One row == one row from preproccessed.csv (stage-03 output).
    All downstream analytics MUST start from this table.
    """

    __tablename__ = "preprocessed_tracks"

    id = Column(String(64), primary_key=True, index=True)
    name = Column(String(512), nullable=True)
    album = Column(String(512), nullable=True)
    album_id = Column(String(64), nullable=True, index=True)
    artists = Column(Text, nullable=True)
    artist_ids = Column(Text, nullable=True)

    track_number = Column(Integer, nullable=True)
    disc_number = Column(Integer, nullable=True)
    explicit = Column(Boolean, nullable=True)
    duration_ms = Column(Integer, nullable=True)
    year = Column(Integer, nullable=True)
    release_date = Column(String(32), nullable=True)

    danceability = Column(Float, nullable=True)
    energy = Column(Float, nullable=True)
    key = Column(Integer, nullable=True)
    loudness = Column(Float, nullable=True)
    mode = Column(Integer, nullable=True)
    speechiness = Column(Float, nullable=True)
    acousticness = Column(Float, nullable=True)
    instrumentalness = Column(Float, nullable=True)
    liveness = Column(Float, nullable=True)
    valence = Column(Float, nullable=True)
    tempo = Column(Float, nullable=True)
    time_signature = Column(Integer, nullable=True)

    lyrics = Column(Text, nullable=True)
    lyrics_source = Column(String(256), nullable=True)
    lyrics_path = Column(String(512), nullable=True)

    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


# Dimension tables rebuilt from preprocessed_tracks
class DimAlbum(Base):
    """
    Album dimension derived from distinct (album_id, album title) pairs in preprocessed.
    """

    __tablename__ = "dim_albums"

    id = Column(String(64), primary_key=True, index=True)
    title = Column(String(512), nullable=False)
    track_count = Column(Integer, nullable=True)
    metrics_json = Column(JSON, nullable=True)
    updated_at = Column(DateTime(timezone=True), nullable=True)
    color = Column(String(7), nullable=True)
    # Deduplicated image id from pipeline ``image.db`` / ``album_covers.db`` (0 = placeholder).
    cover_image_id = Column(Integer, nullable=True)


class DimArtist(Base):
    """
    Artist dimension derived from artist_ids appearing in preprocessed rows.
    """

    __tablename__ = "dim_artists"

    id = Column(String(64), primary_key=True, index=True)
    name = Column(String(512), nullable=False)
    track_count = Column(Integer, nullable=True)
    metrics_json = Column(JSON, nullable=True)
    updated_at = Column(DateTime(timezone=True), nullable=True)
    color = Column(String(7), nullable=True)
    cover_image_id = Column(Integer, nullable=True)


class BridgeTrackArtist(Base):
    """
    Many-to-many track-artist.
    """

    __tablename__ = "bridge_track_artists"
    __table_args__ = (
        UniqueConstraint("track_id", "artist_id", name="uq_track_artist"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)

    track_id = Column(String(64), ForeignKey("preprocessed_tracks.id", ondelete="CASCADE"), nullable=False, index=True)
    artist_id = Column(String(64), ForeignKey("dim_artists.id", ondelete="CASCADE"), nullable=False, index=True)


class FactTrackAudioFeatures(Base):
    """
    Optional split table: same numeric audio fields but stored as a fact row.
    Rebuilt from preprocessed_tracks (copy).
    """

    __tablename__ = "fact_track_audio_features"

    track_id = Column(String(64), ForeignKey("preprocessed_tracks.id", ondelete="CASCADE"), primary_key=True)

    danceability = Column(Float, nullable=True)
    energy = Column(Float, nullable=True)
    key = Column(Integer, nullable=True)
    loudness = Column(Float, nullable=True)
    mode = Column(Integer, nullable=True)
    speechiness = Column(Float, nullable=True)
    acousticness = Column(Float, nullable=True)
    instrumentalness = Column(Float, nullable=True)
    liveness = Column(Float, nullable=True)
    valence = Column(Float, nullable=True)
    tempo = Column(Float, nullable=True)
    time_signature = Column(Integer, nullable=True)


# Galaxy + clusters (results of analysis)
class DimCluster(Base):
    """
    Cluster dictionary for UI / joins.
    """

    __tablename__ = "dim_clusters"

    id = Column(Integer, primary_key=True, autoincrement=True)

    code = Column(String(32), nullable=False, index=True)
    name = Column(String(256), nullable=True)
    track_count = Column(Integer, nullable=True)
    metrics_json = Column(JSON, nullable=True)
    description = Column(Text, nullable=True)
    llm_model = Column(String(128), nullable=True)
    llm_updated_at = Column(DateTime(timezone=True), nullable=True)
    color = Column(String(7), nullable=True)

    __table_args__ = (UniqueConstraint("code", name="uq_dim_cluster_code"),)


class FactGalaxyPoint(Base):
    """
    Galaxy point for one track (coordinates + optional lyric/audio scores).
    """

    __tablename__ = "fact_galaxy_points"

    track_id = Column(String(64), ForeignKey("preprocessed_tracks.id", ondelete="CASCADE"), primary_key=True)

    x = Column(Float, nullable=False)
    y = Column(Float, nullable=False)
    z = Column(Float, nullable=False, default=0.0)

    # LLM / derived coloring fields if present in embeded_data.csv
    lyrical_intensity = Column(Float, nullable=True)
    lyrical_mood = Column(Float, nullable=True)

    energy = Column(Float, nullable=True)
    valence = Column(Float, nullable=True)
    color = Column(String(7), nullable=True)

    # Cluster id/code from pipeline output (single cluster dimension)
    cluster_code = Column(String(32), nullable=True, index=True)

    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class BridgeTrackCluster(Base):
    """
    Normalized cluster membership.
    """

    __tablename__ = "bridge_track_clusters"

    id = Column(Integer, primary_key=True, autoincrement=True)

    track_id = Column(String(64), ForeignKey("preprocessed_tracks.id", ondelete="CASCADE"), nullable=False, index=True)
    cluster_id = Column(Integer, ForeignKey("dim_clusters.id", ondelete="CASCADE"), nullable=False, index=True)

    __table_args__ = (UniqueConstraint("track_id", "cluster_id", name="uq_track_cluster"),)


class Song(Base):
    __tablename__ = "songs"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    artists = Column(Text, nullable=False)
    album = Column(String, nullable=False)
    album_id = Column(String, nullable=False)
    lyrics = Column(Text, nullable=False)