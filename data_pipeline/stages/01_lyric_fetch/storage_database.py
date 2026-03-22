import dataclasses
import json
import sqlite3
import threading
from typing import Any, Dict, Optional, Union
from dataclasses import dataclass
from parsers import LyricEntry


class LyricDatabase:
    """
    Thread‑safe SQLite database for storing LyricEntry objects indexed by song_id.

    Each thread gets its own database connection. Write operations (insert/update/delete)
    are serialized with a lock to avoid "database is locked" errors. Read operations
    can be performed concurrently.

    The database is created with WAL mode enabled for better concurrency.
    """

    def __init__(self, db_path: str):
        """
        Initialize the database.

        Args:
            db_path: Filesystem path to the SQLite database file.
        """
        self.db_path = db_path
        self._local = threading.local()
        self._write_lock = threading.Lock()

        # Create the table if it doesn't exist, and enable WAL mode.
        with self._write_lock:
            conn = self._get_connection()
            conn.execute("""
                CREATE TABLE IF NOT EXISTS lyrics (
                    song_id TEXT PRIMARY KEY,
                    matched_name TEXT NOT NULL,
                    matched_album TEXT,
                    matched_artist TEXT NOT NULL,
                    lyrics TEXT,
                    lyrics_instrumental INTEGER,
                    lyrics_source TEXT NOT NULL,
                    raw_response TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS failed(
                         song_id TEXT PRIMARY KEY
                )          
            """)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.commit()

    def _get_connection(self) -> sqlite3.Connection:
        """
        Return a thread‑local SQLite connection.

        If the current thread doesn't have a connection yet, one is created
        with check_same_thread=False to allow reuse across methods in the same
        thread. Row factory is set to sqlite3.Row for convenient column access.
        """
        if not hasattr(self._local, "conn"):
            conn = sqlite3.connect(
                self.db_path,
                timeout=10.0,               # seconds to wait before raising lock error
                check_same_thread=False,     # we manage thread safety ourselves
                isolation_level=None,        # autocommit mode (BEGIN immediately for transactions)
            )
            conn.row_factory = sqlite3.Row
            self._local.conn = conn
        return self._local.conn

    def _serialize_entry(self, entry: LyricEntry) -> Dict[str, Any]:
        """Convert a LyricEntry to a dictionary suitable for database insertion."""
        data = dataclasses.asdict(entry)
        # Convert bool/None to integer for SQLite
        inst = data["lyrics_instrumental"]
        if inst is None:
            data["lyrics_instrumental"] = None
        else:
            data["lyrics_instrumental"] = 1 if inst else 0
        # Serialize raw_response to JSON
        data["raw_response"] = json.dumps(data["raw_response"], ensure_ascii=False)
        return data

    def _deserialize_row(self, row: sqlite3.Row) -> LyricEntry:
        """Convert a database row (sqlite3.Row) back to a LyricEntry."""
        data = dict(row)
        # Convert integer back to bool/None
        inst_val = data["lyrics_instrumental"]
        if inst_val is None:
            data["lyrics_instrumental"] = None
        else:
            data["lyrics_instrumental"] = bool(inst_val)
        # Deserialize JSON
        data["raw_response"] = json.loads(data["raw_response"])
        return LyricEntry(**data)

    def insert_failure(self, song_id: str) -> None:
        with self._write_lock:
            conn = self._get_connection()
            conn.execute("""
                INSERT OR REPLACE 
                         INTO failed (song_id) 
                         VALUES (?);
            """, (song_id, ))
            conn.commit()

    def exists(self, song_id: str) -> bool:
        with self._write_lock:
            conn = self._get_connection()
            cursor = conn.execute("""
            SELECT (
                EXISTS (
                         SELECT 1 FROM failed WHERE song_id = ?
                    ) OR 
                EXISTS (
                         SELECT 1 FROM lyrics WHERE song_id = ?
                    )
            ) AS present
            """, (song_id, song_id))
            return bool(cursor.fetchone()[0])

    def insert_or_update(self, song_id: str, entry: LyricEntry) -> None:
        """
        Insert or replace a LyricEntry for the given song_id.

        This operation is serialized with a lock to ensure thread safety.

        Args:
            song_id: Primary key.
            entry: The LyricEntry object to store.
        """
        data = self._serialize_entry(entry)
        data["song_id"] = song_id

        with self._write_lock:
            conn = self._get_connection()
            conn.execute("""
                INSERT OR REPLACE INTO lyrics (
                    song_id, matched_name, matched_album, matched_artist,
                    lyrics, lyrics_instrumental, lyrics_source, raw_response
                ) VALUES (
                    :song_id, :matched_name, :matched_album, :matched_artist,
                    :lyrics, :lyrics_instrumental, :lyrics_source, :raw_response
                )
            """, data)
            conn.commit()

    def get(self, song_id: str) -> Optional[LyricEntry]:
        """
        Retrieve the LyricEntry for a given song_id.

        Args:
            song_id: The primary key to look up.

        Returns:
            The LyricEntry if found, otherwise None.
        """
        conn = self._get_connection()
        cursor = conn.execute(
            "SELECT * FROM lyrics WHERE song_id = ?",
            (song_id,)
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return self._deserialize_row(row)

    def delete(self, song_id: str) -> bool:
        """
        Delete the entry for the given song_id.

        Args:
            song_id: The primary key to delete.

        Returns:
            True if a row was deleted, False otherwise.
        """
        with self._write_lock:
            conn = self._get_connection()
            cursor = conn.execute(
                "DELETE FROM lyrics WHERE song_id = ?",
                (song_id,)
            )
            conn.commit()
            return cursor.rowcount > 0

    def contains(self, song_id: str) -> bool:
        """
        Check whether an entry exists for the given song_id.

        Args:
            song_id: The primary key to check.

        Returns:
            True if the key exists, False otherwise.
        """
        conn = self._get_connection()
        cursor = conn.execute(
            "SELECT 1 FROM lyrics WHERE song_id = ?",
            (song_id,)
        )
        return cursor.fetchone() is not None

    def close(self) -> None:
        """
        Close all database connections opened by any thread.

        This should be called when the database is no longer needed,
        typically at program shutdown.
        """
        if hasattr(self._local, "conn"):
            self._local.conn.close()
            del self._local.conn

        # There might be connections in other threads stored in _local.
        # We cannot easily iterate over them. A common pattern is to
        # rely on each thread closing its own connection, or to use a
        # finalizer. For simplicity, this method only closes the connection
        # of the calling thread. A more robust solution would involve
        # tracking all created connections, but that is left as an exercise.