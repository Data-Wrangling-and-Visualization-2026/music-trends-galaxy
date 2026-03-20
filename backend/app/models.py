from sqlalchemy import Column, Integer, String, Text, Float
from .database import Base


class Song(Base):
    __tablename__ = "songs"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    artists = Column(Text, nullable=False)  # JSON array stored as text
    album = Column(String, nullable=False)
    album_id = Column(String, nullable=False)
    lyrics = Column(Text, nullable=False)


class GalaxyTrack(Base):
    """Tracks from embeded_data.csv, seeded at container startup."""

    __tablename__ = "galaxy_tracks"

    id = Column(String, primary_key=True, index=True)  # Spotify id
    name = Column(String, nullable=False)
    album = Column(String, nullable=True)
    album_id = Column(String, nullable=True)
    artists = Column(Text, nullable=True)  # JSON array or raw string
    x_coord = Column(Float, nullable=False)
    y_coord = Column(Float, nullable=False)
    lyrical_intensity = Column(Float, nullable=True)
    lyrical_mood = Column(Float, nullable=True)
    energy = Column(Float, nullable=True)
    valence = Column(Float, nullable=True)
    lyrics = Column(Text, nullable=True)