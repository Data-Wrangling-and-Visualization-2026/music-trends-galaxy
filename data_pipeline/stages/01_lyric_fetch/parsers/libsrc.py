import re
from collections.abc import Iterable
import dataclasses
from typing import Any, Dict, List, Optional

import requests

from .base import BaseParser
from .types import LyricEntry, SongEntry


@dataclasses.dataclass
class LyricsRecordLibSRC:
    """
    Internal representation of a single LRCLib search result.

    This keeps the full LRCLib payload plus some convenience fields for
    matching. It is not exposed outside this module; external callers should
    work with `LyricEntry` instead.
    """

    id: Optional[int]
    track_name: str
    artist_name: str
    album_name: Optional[str]
    duration: Optional[float]
    instrumental: bool
    plain_lyrics: Optional[str]
    synced_lyrics: Optional[str]
    raw: Dict[str, Any]

    def to_lyric_entry(self) -> LyricEntry:
        """
        Convert this LRCLib-specific record into the generic `LyricEntry`.

        We intentionally expose only:
        - matched track / artist / album
        - a single (preferably unsynced) lyrics string, if available
        - instrumental flag
        - the logical source name
        - the raw provider response for advanced use-cases
        """
        return LyricEntry(
            matched_name=self.track_name,
            matched_album=self.album_name,
            matched_artist=self.artist_name,
            lyrics=self.plain_lyrics,
            lyrics_instrumental=self.instrumental,
            lyrics_source="lrclib",
            raw_response=self.raw,
        )

class LRCLibParser(BaseParser):
    """
    LRCLib API implementation of the lyrics provider interface.

    Provides:
    - HTTP access with a persistent `requests.Session`
    - Conversion of raw API responses into internal records, then `LyricEntry`
    - Search, exact lookup, best-match resolution, and unsynced text extraction
    """

    BASE_URL = "https://lrclib.net/api"
    session: requests.Session
    timeout: int

    def __init__(self, timeout: int = 15):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (compatible; LRCLibParser/1.0)",
                "Accept": "application/json",
            }
        )

    def _get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """
        Perform a GET request against the LRCLib API and return decoded JSON.

        Returns `None` for 404 responses and raises for other HTTP errors.
        """
        url = f"{self.BASE_URL}{endpoint}"
        response = self.session.get(url, params=params, timeout=self.timeout)

        if response.status_code == 404:
            return None

        response.raise_for_status()
        return response.json()
        
    def _to_record(self, item: Dict[str, Any]) -> LyricsRecordLibSRC:
        """
        Convert a raw LRCLib response item into a `LyricsRecordLibSRC`.
        """
        return LyricsRecordLibSRC(
            id=item.get("id"),
            track_name=item.get("trackName") or item.get("name") or "",
            artist_name=item.get("artistName") or "",
            album_name=item.get("albumName"),
            duration=item.get("duration"),
            instrumental=bool(item.get("instrumental", False)),
            plain_lyrics=item.get("plainLyrics"),
            synced_lyrics=item.get("syncedLyrics"),
            raw=item,
        )
        
    @staticmethod
    def _norm(s: Optional[str]) -> str:
        """
        Normalize a string for comparison: safe, stripped and lower‑cased.
        """
        return (s or "").strip().lower()
        
    def _search_records(
        self,
        *,
        track_name: Optional[str] = None,
        artist_name: Optional[str] = None,
        album_name: Optional[str] = None,
        q: Optional[str] = None,
    ) -> List[LyricsRecordLibSRC]:
        """
        Low-level search that returns provider-specific records.

        Used internally for matching logic; public callers should prefer
        `search`, which returns `LyricEntry` values.
        """
        params: Dict[str, Any] = {}

        if q:
            params["q"] = q
        else:
            if track_name:
                params["track_name"] = track_name
            if artist_name:
                params["artist_name"] = artist_name
            if album_name:
                params["album_name"] = album_name

        data = self._get("/search", params=params)

        if not data:
            return []

        return [self._to_record(item) for item in data]

    def search(
        self,
        *,
        track_name: Optional[str] = None,
        artist_name: Optional[str] = None,
        album_name: Optional[str] = None,
        q: Optional[str] = None,
    ) -> List[LyricEntry]:
        """
        Public search API that returns normalized `LyricEntry` objects.
        """
        records = self._search_records(
            track_name=track_name,
            artist_name=artist_name,
            album_name=album_name,
            q=q,
        )
        return [record.to_lyric_entry() for record in records]
        
    def _get_by_signature_record(
        self,
        *,
        track_name: str,
        artist_name: str,
        album_name: Optional[str] = None,
        duration: Optional[float] = None,
    ) -> Optional[LyricsRecordLibSRC]:
        """
        Low-level exact lookup that returns a provider-specific record.

        Public callers should prefer `get_by_signature`, which returns a
        normalized `LyricEntry`.
        """
        params: Dict[str, Any] = {
            "track_name": track_name,
            "artist_name": artist_name,
        }
        if album_name is not None:
            params["album_name"] = album_name
        if duration is not None:
            params["duration"] = duration

        data = self._get("/get", params=params)
        if not data:
            return None

        return self._to_record(data)

    def get_by_signature(
        self,
        *,
        track_name: str,
        artist_name: str,
        album_name: Optional[str] = None,
        duration: Optional[float] = None,
    ) -> Optional[LyricEntry]:
        """
        Try to resolve a single lyrics record using an exact signature.

        This calls the `/get` endpoint which is more precise than a generic
        search and should be tried first.
        """
        record = self._get_by_signature_record(
            track_name=track_name,
            artist_name=artist_name,
            album_name=album_name,
            duration=duration,
        )
        return record.to_lyric_entry() if record is not None else None
        

    def get_lyrics(
        self,
        *,
        track_name: str,
        artist_name: str,
        album_name: Optional[str] = None,
        duration: Optional[float] = None,
    ) -> LyricEntry:
        """
        Resolve the best lyrics record for the given song metadata.

        The method first tries an exact `/get` call and falls back to the
        `/search` endpoint with a best‑match selection strategy.
        """
        record = self._get_by_signature_record(
            track_name=track_name,
            artist_name=artist_name,
            album_name=album_name,
            duration=duration,
        )
        if record is not None:
            return record.to_lyric_entry()

        # Fallback to search when an exact match cannot be resolved.
        candidates = self._search_records(
            track_name=track_name,
            artist_name=artist_name,
            album_name=album_name,
        )

        if not candidates:
            raise ValueError(
                f"Не удалось найти lyrics для: {artist_name} - {track_name}"
            )

        best_record = self._choose_best_match(
            candidates,
            track_name=track_name,
            artist_name=artist_name,
            album_name=album_name,
        )

        if best_record is None:
            raise ValueError(
                f"Не удалось выбрать подходящий результат для: {artist_name} - {track_name}"
            )

        return best_record.to_lyric_entry()
        

    def _choose_best_match(
        self,
        candidates: List[LyricsRecordLibSRC],
        *,
        track_name: str,
        artist_name: str,
        album_name: Optional[str] = None,
    ) -> Optional[LyricsRecordLibSRC]:
        """
        Heuristically pick the best matching record from a list of candidates.

        The selection is done in several passes:
        1. Exact match on track, artist and album (when album is provided)
        2. Exact match on track and artist
        3. Exact match on track
        4. Fallback to the first candidate, if present
        """
        t = self._norm(track_name)
        a = self._norm(artist_name)
        alb = self._norm(album_name)

        # 1) Exact match on track, artist and album (if album is known).
        for item in candidates:
            if (
                self._norm(item.track_name) == t
                and self._norm(item.artist_name) == a
                and (not alb or self._norm(item.album_name) == alb)
            ):
                return item

        # 2) Exact match on track and artist only.
        for item in candidates:
            if self._norm(item.track_name) == t and self._norm(item.artist_name) == a:
                return item

        # 3) Exact match on track name, whatever the artist.
        for item in candidates:
            if self._norm(item.track_name) == t:
                return item

        # 4) Fallback: just return the first candidate, if any.
        return candidates[0] if candidates else None

    def _synced_to_unsynced(self, lyrics: str) -> str:
        """
        Convert synced (timestamped) lyrics into a plain, unsynced text form.

        The LRCLib synced format is LRC‑like: each line can start with one or
        more `[mm:ss.xx]` / `[hh:mm:ss.xx]` timestamps. This helper strips all
        such markers and keeps only the textual content.
        """
        lines: List[str] = []

        for line in lyrics.splitlines():
            # Remove all time tags and surrounding whitespace.
            text = re.sub(r"\[[0-9:.]+\]\s*", "", line).strip()
            if text:
                lines.append(text)

        return "\n".join(lines)

    def extract_text(
        self,
        record: LyricEntry,
    ) -> str:
        """
        Extract a human‑readable, unsynced lyrics text from a record.

        The order of preference is:
        1. Instrumental marker for instrumental tracks
        2. Pre‑computed plain (unsynced) lyrics
        3. Synced lyrics converted to unsynced text
        4. Empty string if no usable lyrics are available
        """
        if record.lyrics_instrumental:
            return "[Instrumental]"

        if record.lyrics:
            return record.lyrics

        # Try to recover synced lyrics from the raw LRCLib payload and
        # convert them into unsynced text.
        synced = None
        raw = record.raw_response or {}
        if isinstance(raw, dict):
            synced = raw.get("syncedLyrics") or raw.get("synced_lyrics")

        if isinstance(synced, str) and synced.strip():
            return self._synced_to_unsynced(synced)

        return ""
        
    def get_many(
        self,
        songs: Iterable[dict] | Iterable[SongEntry],
        *,
        skip_errors: bool = True,
    ) -> List[LyricEntry]:
        """
        Bulk resolve lyrics; failed items are logged to stdout when skip_errors is True.
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
                    entry = self.get_lyrics(
                        track_name=song["track_name"],
                        artist_name=song["artist_name"],
                        album_name=song.get("album_name"),
                        duration=song.get("duration"),
                    )
                results.append(entry)
            except Exception as e:
                if skip_errors:
                    print(f"[ERROR] {song}: {e}")
                else:
                    raise

        return results