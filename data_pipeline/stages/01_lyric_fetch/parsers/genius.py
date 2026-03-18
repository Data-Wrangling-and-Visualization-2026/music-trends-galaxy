import bs4
import requests
import functools
from urllib.parse import urljoin
from typing import List, Optional

from .base import BaseParser
from .types import LyricEntry, SongEntry


class GeniusParser(BaseParser):
    """
    Lyrics provider implementation that scrapes Genius web pages.
    """

    BASE_URL = "https://genius.com/"

    # Realistic browser headers so Genius serves normal HTML and allows API access
    DEFAULT_HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }

    @staticmethod
    def _get_text_with_linebreaks(element: bs4.PageElement) -> str:
        """
        Extract text from an element, inserting newlines for block-level tags and <br>.
        """
        block_tags = {"p", "li", "ul", "ol", "blockquote", "pre", "hr"}
        result: List[str] = []

        for content in element.children:
            if isinstance(content, bs4.NavigableString):
                text = str(content)
                if text:
                    result.append(text)
            elif isinstance(content, bs4.Tag):
                if content.name == "br":
                    result.append("\n")
                else:
                    inner_text = GeniusParser._get_text_with_linebreaks(content)
                    if inner_text:
                        result.append(inner_text)
                    if content.name in block_tags:
                        result.append("\n")
        return "".join(result)

    @staticmethod
    def _cleanup(text: str) -> str:
        """
        Remove [...]-style annotations from lyrics text.
        """
        lines = (line.strip() for line in text.splitlines())
        lines = (line for line in lines if not (line.startswith("[") and line.endswith("]")))
        return "\n".join(lines)

    @staticmethod
    @functools.lru_cache(maxsize=None)
    def _search_song(artist: str, track: str) -> List[SongEntry]:
        """
        Search Genius for a song; returns a list of matching SongEntry.
        Results are cached to avoid repeated API calls.
        """
        url = "https://genius.com/api/search/multi"
        query = {"q": f"{artist} - {track}", "per_page": 5}

        try:
            response = requests.get(url, params=query, headers=GeniusParser.DEFAULT_HEADERS)
            response.raise_for_status()
            data = response.json()
        except (requests.RequestException, ValueError) as e:
            raise RuntimeError(f"Failed to fetch search results: {e}") from e

        sections = data.get("response", {}).get("sections", [])
        song_sections = [s for s in sections if s.get("type") == "song"]
        if not song_sections:
            return []

        all_hits: List[dict] = []
        for section in song_sections:
            hits = section.get("hits", [])
            all_hits.extend(
                hit["result"] for hit in hits
                if hit.get("type") == "song" and "result" in hit
            )

        entries: List[SongEntry] = []
        for result in all_hits:
            entries.append(
                SongEntry(
                    artis=result.get("artist_names", ""),
                    name=result.get("full_title", ""),
                    path=result.get("path", ""),
                    src="genius",
                )
            )
        return entries

    def _fetch_lyric(self, artist: str, track: str) -> LyricEntry:
        """
        Fetch and parse lyrics for a given artist and track from Genius.
        Returns a LyricEntry with matched metadata, lyrics text, and raw_response.
        """
        entries = self._search_song(artist, track)
        if not entries:
            raise ValueError(f"No entries found for {artist} - {track}")

        entry = entries[0]
        url = urljoin(self.BASE_URL, entry.path)

        response = requests.get(url, headers=GeniusParser.DEFAULT_HEADERS)
        if response.status_code != 200:
            raise ConnectionError(f"Cannot load lyrics page (status {response.status_code})")

        soup = bs4.BeautifulSoup(response.text, "html5lib")
        app_div = soup.find("div", id="application")
        if app_div is None:
            raise LookupError("Could not find application div")

        lyrics_root = app_div.find("div", id="lyrics-root")
        if lyrics_root is None:
            lyrics_root = soup.find("div", {"data-lyrics-container": "true"})
            if lyrics_root is None:
                raise LookupError("Could not find lyrics container")

        if isinstance(lyrics_root, bs4.element.ResultSet):
            lyrics_root = lyrics_root[0]

        lyrics_containers = lyrics_root.find_all(
            "div", class_="Lyrics__Container-sc-d7157b20-1 Mfmpf"
        )
        for lyric_entry in lyrics_containers:
            for trash in lyric_entry.find_all(
                "div", class_="LyricsHeader__Container-sc-2ca6447a-1 cgxMBK"
            ):
                trash.decompose()
            for trash in lyric_entry.find_all(
                "div", class_="LyricsHeader__Container-sc-34356fc0-1 nNOxg"
            ):
                trash.decompose()

        text = "\n".join(
            self._get_text_with_linebreaks(el) for el in lyrics_containers
        )
        text = self._cleanup(text)

        return LyricEntry(
            matched_name=entry.name,
            matched_album=None,
            matched_artist=entry.artis,
            lyrics=text,
            lyrics_instrumental=False,
            lyrics_source="genius",
            raw_response={
                "provider": "genius",
                "artist_names": entry.artis,
                "full_title": entry.name,
                "path": entry.path,
                "url": url,
            },
        )

    def search(
        self,
        *,
        track_name: str | None = None,
        artist_name: str | None = None,
        album_name: str | None = None,  # unused for Genius
        q: str | None = None,
    ) -> List[LyricEntry]:
        artist = artist_name or ""
        track = track_name or ""
        if q:
            artist = ""
            track = q

        song_entries = self._search_song(artist, track)

        results: List[LyricEntry] = []
        for s in song_entries:
            results.append(
                LyricEntry(
                    matched_name=s.name,
                    matched_album=None,
                    matched_artist=s.artis,
                    lyrics=None,  # lyrics are only fetched in get_lyrics
                    lyrics_instrumental=None,
                    lyrics_source="genius",
                    raw_response={
                        "provider": "genius",
                        "artist_names": s.artis,
                        "full_title": s.name,
                        "path": s.path,
                    },
                )
            )

        return results

    def get_by_signature(
        self,
        *,
        track_name: str,
        artist_name: str,
        album_name: str | None = None,
        duration: float | None = None,
    ) -> Optional[LyricEntry]:
        """
        For Genius we approximate an "exact" match by taking the first search hit.
        """
        candidates = self.search(
            track_name=track_name,
            artist_name=artist_name,
            album_name=album_name,
        )
        return candidates[0] if candidates else None

    def get_lyrics(
        self,
        *,
        track_name: str,
        artist_name: str,
        album_name: str | None = None,
        duration: float | None = None,
    ) -> LyricEntry:
        """
        Resolve lyrics by fetching the Genius lyrics page and parsing it.
        """
        return self._fetch_lyric(artist_name, track_name)
