from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable
from typing import List

from .types import LyricEntry, SongEntry


class BaseParser(ABC):
    """
    Abstract base class for all lyrics providers.

    Concrete implementations (e.g. LRCLib, other APIs, local caches) must
    implement this interface so that the rest of the pipeline can work with
    them uniformly via `LyricEntry` / `SongEntry`.
    """

    @abstractmethod
    def search(
        self,
        *,
        track_name: str | None = None,
        artist_name: str | None = None,
        album_name: str | None = None,
        q: str | None = None,
    ) -> List[LyricEntry]:
        """
        Find candidate lyrics entries for the given query.

        - **track_name**: track title to search for (may be `None` when using `q`)
        - **artist_name**: primary artist name (optional)
        - **album_name**: album name (optional)
        - **q**: free-text query, passed directly to the provider when supported

        Implementations may choose to ignore some fields, but they must return
        zero or more `LyricEntry` instances that best match the query.
        """

    @abstractmethod
    def get_by_signature(
        self,
        *,
        track_name: str,
        artist_name: str,
        album_name: str | None = None,
        duration: float | None = None,
    ) -> LyricEntry | None:
        """
        Resolve a single lyrics entry using an exact-ish signature.

        - **track_name**: exact track title
        - **artist_name**: exact artist name
        - **album_name**: exact album name, if known
        - **duration**: track duration in seconds, if available

        Should return `None` when no suitable match can be found.
        """

    @abstractmethod
    def get_lyrics(
        self,
        *,
        track_name: str,
        artist_name: str,
        album_name: str | None = None,
        duration: float | None = None,
    ) -> LyricEntry:
        """
        High-level helper to resolve the *best* lyrics entry for the given song.

        - **track_name**: track title (required)
        - **artist_name**: artist name (required)
        - **album_name**: album name (optional)
        - **duration**: track duration in seconds, used as an extra hint (optional)

        Implementations may internally use `get_by_signature` and/or `search`
        with provider-specific heuristics, but consumers should always call
        this method when they just need "the best available lyrics".
        """

    def get_many(
        self,
        songs: Iterable[dict] | Iterable[SongEntry],
        *,
        skip_errors: bool = True,
    ) -> List[LyricEntry]:
        """
        Bulk helper to resolve lyrics for many songs.

        - **songs**: iterable of song descriptors; can be:
          - plain dicts with at least `track_name` and `artist_name` keys
          - `SongEntry` instances
        - **skip_errors**: when `True` (default), errors for individual songs
          are logged/ignored; when `False`, the first error is re-raised.

        The default implementation iterates over `songs` and calls `get_lyrics`
        for each item. Providers may override this to add concurrency, retry
        logic, rate limiting, batching, etc.
        """
        results: List[LyricEntry] = []

        for song in songs:
            try:
                if isinstance(song, SongEntry):
                    entry = self.get_lyrics(
                        track_name=song.name,
                        artist_name=song.artis,
                        album_name=None,
                        duration=None,
                    )
                else:
                    # Assume a mapping with at least the basic keys.
                    track_name = song.get("track_name")
                    artist_name = song.get("artist_name")
                    album_name = song.get("album_name")
                    duration = song.get("duration")
                    entry = self.get_lyrics(
                        track_name=track_name,
                        artist_name=artist_name,
                        album_name=album_name,
                        duration=duration,
                    )
                results.append(entry)
            except Exception:
                if not skip_errors:
                    raise
                # For the base implementation we simply skip failures; concrete
                # providers can override this to add logging if needed.

        return results

