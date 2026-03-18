from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models import Song
from app.schemas import SongInfo
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

@router.get("/song/{id}", response_model=SongInfo)
def get_song_info(id: int, db: Session = Depends(get_db)):
    song = db.query(Song).filter(Song.id == id).first()
    if not song:
        raise HTTPException(status_code=404, detail="Song not found")
    # Convert artists JSON string to list
    artists = json.loads(song.artists)
    return SongInfo(
        name=song.name,
        artists=artists,
        album=song.album,
        album_id=song.album_id,
        lyrics=song.lyrics,
    )