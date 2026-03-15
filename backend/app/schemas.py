from pydantic import BaseModel, ConfigDict
from typing import List


class SongListItem(BaseModel):
    """Краткая карточка трека для списков (без текста песни)."""

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
