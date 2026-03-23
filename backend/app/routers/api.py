from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session
from typing import List

from app.database import SessionLocal
from app.models import Song
from app.schemas import SongInfo, SongListItem
from app.config import COVERS_DIR
from app.utils.file_handlers import read_image_file
import json

router = APIRouter(prefix="/api", tags=["Runtime"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/cover/{id}.jpeg")
async def get_cover(id: str):
    cover_path = COVERS_DIR / f"{id}.jpeg"
    image_data = await read_image_file(cover_path)
    return Response(content=image_data, media_type="image/jpeg")

def _song_to_list_item(song: Song) -> SongListItem:
    return SongListItem(
        id=song.id,
        name=song.name,
        artists=json.loads(song.artists),
        album=song.album,
        album_id=song.album_id,
    )


@router.get("/songs", response_model=List[SongListItem])
def list_songs(db: Session = Depends(get_db)):
    rows = db.query(Song).order_by(Song.id).all()
    return [_song_to_list_item(s) for s in rows]


@router.get("/song/{id}", response_model=SongInfo)
def get_song_info(id: int, db: Session = Depends(get_db)):
    song = db.query(Song).filter(Song.id == id).first()
    if not song:
        raise HTTPException(status_code=404, detail="Song not found")
    artists = json.loads(song.artists)
    return SongInfo(
        id=song.id,
        name=song.name,
        artists=artists,
        album=song.album,
        album_id=song.album_id,
        lyrics=song.lyrics,
        duration_ms=song.duration_ms,
        danceability=song.danceability,
        energy=song.energy,
        valence=song.valence,
        loudness=song.loudness,
        speechiness=song.speechiness,
        acousticness=song.acousticness,
        instrumentalness=song.instrumentalness,
        liveness=song.liveness,
        tempo=song.tempo,
        year=song.year,
    )