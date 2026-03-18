from pydantic import BaseModel
from typing import List

class SongInfo(BaseModel):
    name: str
    artists: List[str]
    album: str
    album_id: str
    lyrics: str

    class Config:
        orm_mode = True