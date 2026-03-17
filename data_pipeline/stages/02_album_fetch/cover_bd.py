import sqlite3
import json
import threading
from typing import List, Optional
from PIL import Image
import io

from fetchers.types import AlbumCover

class AlbumCoverDB:
    """
    Thread-safe SQLite database for storing album cover information.
    Uses a new connection per operation and enables WAL mode for concurrency.
    """

    def __init__(self, db_path: str, image_format: str = "PNG"):
        """
        Initialize the database connection and create table if not exists.

        :param db_path: Path to the SQLite database file.
        :param image_format: Format to use when saving PIL Image to BLOB (e.g., 'PNG', 'JPEG').
        """
        self.db_path = db_path
        self.image_format = image_format
        self._lock = threading.Lock()  # optional lock for serialization if needed
        self._init_db()

    def _init_db(self):
        """Create the table and set WAL mode for better concurrency."""
        with self._get_connection() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS album_covers (
                    album_id TEXT PRIMARY KEY,
                    album_name TEXT NOT NULL,
                    artists TEXT NOT NULL,       -- JSON array
                    image_path TEXT NOT NULL,
                    image_source TEXT NOT NULL,
                    image BLOB NOT NULL           -- raw image data
                )
            """)

    def _get_connection(self):
        """
        Return a new SQLite connection with row factory and threading support.
        The connection is used as a context manager to auto-commit/close.
        """
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    # ---------- Serialization helpers ----------
    def _artists_to_json(self, artists: List[str]) -> str:
        return json.dumps(artists, ensure_ascii=False)

    def _json_to_artists(self, data: str) -> List[str]:
        return json.loads(data) if data else []

    def _image_to_bytes(self, image: Image.Image) -> bytes:
        buffer = io.BytesIO()
        image.save(buffer, format=self.image_format)
        return buffer.getvalue()

    def _bytes_to_image(self, data: bytes) -> Image.Image:
        return Image.open(io.BytesIO(data))

    # ---------- Public API ----------
    def insert_or_replace(self, cover: AlbumCover) -> None:
        """
        Insert a new album cover or replace an existing one.
        """
        with self._get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO album_covers
                (album_id, album_name, artists, image_path, image_source, image)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                cover.album_id,
                cover.album_name,
                self._artists_to_json(cover.artists),
                cover.image_path,
                cover.image_source,
                self._image_to_bytes(cover.image)
            ))

    def get(self, album_id: str) -> Optional[AlbumCover]:
        """
        Retrieve an album cover by its ID. Returns None if not found.
        """
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM album_covers WHERE album_id = ?",
                (album_id,)
            ).fetchone()

        if row is None:
            return None

        return AlbumCover(
            album_id=row["album_id"],
            album_name=row["album_name"],
            artists=self._json_to_artists(row["artists"]),
            image_path=row["image_path"],
            image_source=row["image_source"],
            image=self._bytes_to_image(row["image"])
        )

    def exists(self, album_id: str) -> bool:
        """
        Check if an album cover with the given ID exists in the database.

        :param album_id: The album ID to check.
        :return: True if the album exists, False otherwise.
        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT EXISTS(SELECT 1 FROM album_covers WHERE album_id = ?)",
                (album_id,)
            )
            # EXISTS returns 0 or 1
            result = cursor.fetchone()[0]
            return bool(result)

    def delete(self, album_id: str) -> bool:
        """
        Delete the album cover with the given ID. Returns True if a row was deleted.
        """
        with self._get_connection() as conn:
            cursor = conn.execute("DELETE FROM album_covers WHERE album_id = ?", (album_id,))
            return cursor.rowcount > 0

    def list_all(self) -> List[AlbumCover]:
        """
        Return all stored album covers.
        """
        with self._get_connection() as conn:
            rows = conn.execute("SELECT * FROM album_covers").fetchall()

        covers = []
        for row in rows:
            covers.append(AlbumCover(
                album_id=row["album_id"],
                album_name=row["album_name"],
                artists=self._json_to_artists(row["artists"]),
                image_path=row["image_path"],
                image_source=row["image_source"],
                image=self._bytes_to_image(row["image"])
            ))
        return covers

    def close(self):
        """No persistent connection to close; kept for interface compatibility."""
        pass