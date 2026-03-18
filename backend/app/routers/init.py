from fastapi import APIRouter, Response
from app.config import DATA_DIR, CHUNKS_DIR
from app.utils.file_handlers import read_msgpack_file
import json

router = APIRouter(prefix="/init", tags=["Initialization"])

@router.get("/manifest.json")
async def get_manifest():
    manifest_path = DATA_DIR / "manifest.json"
    try:
        with open(manifest_path, "r") as f:
            content = json.load(f)
        return content
    except FileNotFoundError:
        return Response(status_code=404, content="Manifest not found")

@router.get("/chunk/{chunk_name}")
async def get_chunk(chunk_name: str):
    chunk_path = CHUNKS_DIR / chunk_name
    # Ensure .msgpack extension is present (optional)
    if not chunk_path.suffix:
        chunk_path = chunk_path.with_suffix(".msgpack")
    data = await read_msgpack_file(chunk_path)
    # Return as binary msgpack
    return Response(content=msgpack.packb(data, default=str), media_type="application/msgpack")