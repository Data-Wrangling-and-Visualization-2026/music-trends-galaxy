import msgpack
import aiofiles
from fastapi import HTTPException
from pathlib import Path

async def read_msgpack_file(file_path: Path):
    try:
        async with aiofiles.open(file_path, "rb") as f:
            data = await f.read()
        return msgpack.unpackb(data, raw=False)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Chunk not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading chunk: {e}")

async def read_image_file(file_path: Path):
    try:
        async with aiofiles.open(file_path, "rb") as f:
            return await f.read()
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Cover not found")