from sqlalchemy import Column, Integer, String, Text
from .database import Base

class Song(Base):
    __tablename__ = "songs"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    artists = Column(Text, nullable=False)  # JSON array stored as text
    album = Column(String, nullable=False)
    album_id = Column(String, nullable=False)
    lyrics = Column(Text, nullable=False)