import os
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
CHUNKS_DIR = DATA_DIR / "chunks"
COVERS_DIR = DATA_DIR / "covers"
DATABASE_URL = f"sqlite:///{DATA_DIR / 'database.sqlite'}?mode=ro"

def _default_galaxy_csv_path() -> Path:
    """Repo ../storage when that folder exists; otherwise backend/storage (Docker volume)."""
    repo_storage_dir = BASE_DIR.parent / "storage"
    if repo_storage_dir.is_dir():
        return repo_storage_dir / "embeded_data.csv"
    return BASE_DIR / "storage" / "embeded_data.csv"


GALAXY_CSV_PATH = Path(os.getenv("GALAXY_CSV_PATH", str(_default_galaxy_csv_path())))