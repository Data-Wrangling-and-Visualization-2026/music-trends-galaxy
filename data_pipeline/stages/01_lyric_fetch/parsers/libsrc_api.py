import requests
from typing import List, Dict, Optional, Any
from types import LyricsRecordLibSRC


class LRCLibParser:
    BASE_URL = "https://lrclib.net/api"

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
        url = f"{self.BASE_URL}{endpoint}"
        response = self.session.get(url, params=params, timeout=self.timeout)

        if response.status_code == 404:
            return None

        response.raise_for_status()
        return response.json()
        
    def _to_record(self, item: Dict[str, Any]) -> LyricsRecordLibSRC:
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
        return (s or "").strip().lower()
        
    def search(
        self,
        *,
        track_name: Optional[str] = None,
        artist_name: Optional[str] = None,
        album_name: Optional[str] = None,
        q: Optional[str] = None,
    ) -> List[LyricsRecordLibSRC]:
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
        
    def get_by_signature(
        self,
        *,
        track_name: str,
        artist_name: str,
        album_name: Optional[str] = None,
        duration: Optional[float] = None,
    ) -> Optional[LyricsRecordLibSRC]:
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
        

    def get_lyrics(
        self,
        *,
        track_name: str,
        artist_name: str,
        album_name: Optional[str] = None,
        duration: Optional[float] = None,
        prefer_synced: bool = False,
    ) -> LyricsRecordLibSRC:
        exact = self.get_by_signature(
            track_name=track_name,
            artist_name=artist_name,
            album_name=album_name,
            duration=duration,
        )
        if exact:
            return exact

        candidates = self.search(
            track_name=track_name,
            artist_name=artist_name,
            album_name=album_name,
        )

        if not candidates:
            raise ValueError(
                f"Не удалось найти lyrics для: {artist_name} - {track_name}"
            )

        best = self._choose_best_match(
            candidates,
            track_name=track_name,
            artist_name=artist_name,
            album_name=album_name,
        )

        if best is None:
            raise ValueError(
                f"Не удалось выбрать подходящий результат для: {artist_name} - {track_name}"
            )

        return best
        

    def _choose_best_match(
        self,
        candidates: List[LyricsRecordLibSRC],
        *,
        track_name: str,
        artist_name: str,
        album_name: Optional[str] = None,
    ) -> Optional[LyricsRecordLibSRC]:
        t = self._norm(track_name)
        a = self._norm(artist_name)
        alb = self._norm(album_name)

        for item in candidates:
            if (
                self._norm(item.track_name) == t
                and self._norm(item.artist_name) == a
                and (not alb or self._norm(item.album_name) == alb)
            ):
                return item

        for item in candidates:
            if self._norm(item.track_name) == t and self._norm(item.artist_name) == a:
                return item

        for item in candidates:
            if self._norm(item.track_name) == t:
                return item

        return candidates[0] if candidates else None
        

    def extract_text(
        self,
        record: LyricsRecordLibSRC,
        *,
        prefer_synced: bool = False,
    ) -> str:
        if record.instrumental:
            return "[Instrumental]"

        if prefer_synced and record.synced_lyrics:
            return record.synced_lyrics

        if record.plain_lyrics:
            return record.plain_lyrics

        if record.synced_lyrics:
            return record.synced_lyrics

        return ""
        
    def get_many(
        self,
        songs: Iterable[dict],
        *,
        prefer_synced: bool = False,
        skip_errors: bool = True,
    ) -> List[LyricsRecordLibSRC]:
        results: List[LyricsRecordLibSRC] = []

        for song in songs:
            try:
                item = self.get_lyrics(
                    track_name=song["track_name"],
                    artist_name=song["artist_name"],
                    album_name=song.get("album_name"),
                    duration=song.get("duration"),
                    prefer_synced=prefer_synced,
                )
                results.append(item)
            except Exception as e:
                if skip_errors:
                    print(f"[ERROR] {song}: {e}")
                else:
                    raise

        return results

