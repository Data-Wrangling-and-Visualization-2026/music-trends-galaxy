import os
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
CHUNKS_DIR = DATA_DIR / "chunks"
COVERS_DIR = DATA_DIR / "covers"
DATABASE_URL = f"sqlite:///{DATA_DIR / 'database.sqlite'}?mode=ro"