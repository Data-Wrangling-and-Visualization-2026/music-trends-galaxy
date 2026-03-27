from pathlib import Path
import os

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
CHUNKS_DIR = DATA_DIR / "chunks"
COVERS_DIR = DATA_DIR / "covers"


def _load_env_file(path: Path) -> None:
    """Set missing keys from a simple ``KEY=value`` file (local ``backend/.env``)."""
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        if not key or key in os.environ:
            continue
        val = val.strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'":
            val = val[1:-1]
        os.environ[key] = val


_load_env_file(BASE_DIR / ".env")

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL is not set. Add it to backend/.env (see backend/.env.example) "
        "or export it in the shell, e.g. for docker-compose Postgres on the host: "
        "postgresql+psycopg2://app:app@localhost:5433/app"
    )

# Repo / Docker: mounted storage (see docker-compose STORAGE_DIR). Cover pipeline SQLite + JPEGs.
STORAGE_DIR = Path(os.environ.get("STORAGE_DIR", BASE_DIR.parent / "storage")).resolve()
IMAGE_DB_PATH = Path(os.environ.get("IMAGE_DB_PATH", str(STORAGE_DIR / "images" / "image.db"))).resolve()
# Files named ``{image_id}.jpg`` (stage 02 album fetch output).
COVER_STORAGE_FILES_DIR = Path(
    os.environ.get("COVER_STORAGE_FILES_DIR", str(STORAGE_DIR / "images" / "images"))
).resolve()
