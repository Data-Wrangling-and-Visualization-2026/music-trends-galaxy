import sqlite3
import threading
import json
import dataclasses
from typing import List, Optional
from fetchers import AlbumCover

class AlbumCoverDB:
    """
    Thread‑safe SQLite storage for AlbumCover objects.
    Each thread maintains its own connection using thread‑local storage.
    """

    def __init__(self, db_path: str = "album_covers.db"):
        self.db_path = db_path
        self._local = threading.local()
        self._init_db()

    def _init_db(self) -> None:
        """Create the table and set WAL mode (using a temporary connection)."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("PRAGMA journal_mode = WAL")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS album_covers (
                    album_id TEXT PRIMARY KEY,
                    album_name TEXT NOT NULL,
                    artists TEXT NOT NULL,
                    image_path TEXT,
                    image_source TEXT,
                    additional_info TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS failed_album_covers (
                    album_id TEXT PRIMARY KEY,
                    album_name TEXT NOT NULL,
                    artists TEXT NOT NULL
                )
            """)

    def _get_connection(self) -> sqlite3.Connection:
        """Obtain a thread‑local SQLite connection."""
        if not hasattr(self._local, "conn"):
            conn = sqlite3.connect(self.db_path, timeout=10)
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute("PRAGMA journal_mode = WAL")   # already set, but safe to repeat
            self._local.conn = conn
        return self._local.conn

    def save(self, album: AlbumCover) -> None:
        """
        Insert or replace an AlbumCover record.
        Converts lists and dictionaries to JSON strings for storage.
        """
        conn = self._get_connection()
        artists_json = json.dumps(album.artists)
        additional_json = json.dumps(album.additional_info)

        with conn:   # auto‑commit / rollback on exception
            conn.execute("""
                INSERT OR REPLACE INTO album_covers
                (album_id, album_name, artists, image_path, image_source, additional_info)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (album.album_id, album.album_name, artists_json,
                  album.image_path, album.image_source, additional_json))
            
            conn.execute("""
                DELETE FROM failed_album_covers
                WHERE album_id = ?
            """, (album.album_id, ))
            
    def save_failed(self, album: AlbumCover) -> None:
        """
        Insert or replace an AlbumCover record.
        Converts lists and dictionaries to JSON strings for storage.
        """
        conn = self._get_connection()
        artists_json = json.dumps(album.artists)

        with conn:   # auto‑commit / rollback on exception
            conn.execute("""
                INSERT OR REPLACE INTO failed_album_covers
                (album_id, album_name, artists)
                VALUES (?, ?, ?)
            """, (album.album_id, album.album_name, artists_json))

    def failed_to_load(self, album_id: str) -> bool:
        conn = self._get_connection()
        cursor = conn.execute('''
        SELECT * 
        FROM failed_album_covers
        WHERE album_id = ?
''', (album_id,))
        row = cursor.fetchone()

        return row is not None

    def get(self, album_id: str) -> Optional[AlbumCover]:
        """
        Retrieve an AlbumCover by its ID.
        Returns None if not found.
        """
        conn = self._get_connection()
        cursor = conn.execute("""
            SELECT album_id, album_name, artists, image_path, image_source, additional_info
            FROM album_covers
            WHERE album_id = ?
        """, (album_id,))
        row = cursor.fetchone()
        if row is None:
            return None

        return AlbumCover(
            album_id=row[0],
            album_name=row[1],
            artists=json.loads(row[2]),
            image_path=row[3],
            image_source=row[4],
            additional_info=json.loads(row[5]) if row[5] else {},
            image=None
        )

    def close_current_thread_connection(self) -> None:
        """Close the connection for the current thread (if one exists)."""
        if hasattr(self._local, "conn"):
            self._local.conn.close()
            del self._local.conn