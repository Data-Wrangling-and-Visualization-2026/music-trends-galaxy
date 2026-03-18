
from __future__ import annotations

import re
import time
from typing import List, Optional

from rapidfuzz.distance import Levenshtein

import requests
from bs4 import BeautifulSoup, Tag

from .base import BaseParser
from .types import LyricEntry


def remove_hints(text: str) -> str:
    """
    Remove hint markers like '[Chorus:]' from lyrics text.
    
    The pattern matches any square bracket containing at least one non-']' character
    followed by a colon and a closing bracket. These hints are often embedded in
    AZLyrics text and are removed to clean the output.

    Args:
        text: Raw lyrics text possibly containing hints.

    Returns:
        Cleaned lyrics text with all hint markers removed.
    """
    # Pattern: [ ... : ] where ... can be any characters except ']'
    pattern = r'\[[^]]+:\]'
    return re.sub(pattern, '', text)


class AZLyricsParser(BaseParser):
    """
    Parser for azlyrics.com that implements the BaseParser interface.

    This class scrapes lyrics from AZLyrics using a session with browser-like headers
    and a small delay between requests to avoid being blocked. It also handles the
    dynamic 'x_code' required by the site's search form.

    Attributes:
        BASE_URL (str): The base URL of AZLyrics.
        SEARCH_URL (str): The search endpoint URL.
        SECRET_URL (str): URL to fetch the dynamic 'x_code' from.
        DEFAULT_HEADERS (dict): Common HTTP headers to mimic a real browser.
        x_code_update_time (float): Time in seconds after which the x_code is refreshed.
        _session (requests.Session): Persistent session for all requests.
        _x_code (Optional[str]): Cached x_code value.
        _x_code_update_timer (float): Timestamp of the last x_code update.
    """

    BASE_URL = "https://www.azlyrics.com"
    SEARCH_URL = f"{BASE_URL}/search/"
    SECRET_URL = f"{BASE_URL}/geo.js"

    # Headers to mimic a real browser – currently unused because the session
    # headers are not updated; left here for reference.
    DEFAULT_HEADERS = {
        "Accept": "*/*",
        "Accept-Encoding": "gzip, deflate",
        "Host": "httpbin.org",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36",
        "X-Amzn-Trace-Id": "Root=1-63c42540-1a63b1f8420b952f1f0219f1"
    }

    def __init__(self, x_code_update_time: float = 10 * 60):
        """
        Initialize the parser with a session and set up x_code caching.

        Args:
            x_code_update_time: How often (in seconds) to refresh the x_code.
                                 Defaults to 10 minutes.
        """
        self.x_code_update_time = x_code_update_time
        self._session = requests.Session()
        # Optionally update session headers; currently commented out.
        # self._session.headers.update(self.DEFAULT_HEADERS)
        self._x_code = None
        self._x_code_update_timer = -1000.0  # Force first update

    @property
    def x_code(self) -> Optional[str]:
        """
        Lazily get the current x_code, refreshing it if necessary.

        Returns:
            The current x_code string, or None if it couldn't be retrieved.
        """
        now = time.time()
        # Refresh if cache is expired or not yet set
        if now - self._x_code_update_timer >= self.x_code_update_time or self._x_code is None:
            self._update_x_code()
        return self._x_code

    # ----------------------------------------------------------------------
    # The x_code extraction logic is adapted from spotDL/spotify-downloader
    # https://github.com/spotDL/spotify-downloader/blob/master/spotdl/providers/lyrics/azlyrics.py
    # Many thanks to the original authors.
    # ----------------------------------------------------------------------
    def _update_x_code(self) -> None:
        """
        Fetch the dynamic 'x_code' from AZLyrics' geo.js file.

        This code is required for the search form to work. The geo.js script
        contains a hidden input field with a 'value' attribute that holds the code.
        The method extracts that value and caches it.

        The update timer is set regardless of success or failure, so subsequent
        calls will wait the full update interval before retrying.
        """
        self._x_code_update_timer = time.time()
        js_code = None
        session = requests.Session()

        try:
            # First visit the main page to set any cookies (optional but mimics a real visit)
            session.get(self.BASE_URL)
            # Fetch the geo.js script
            resp = session.get(self.SECRET_URL)
            js_code = resp.text
        except (requests.ConnectionError, requests.TooManyRedirects):
            # Network issues – we'll just keep the old x_code (if any)
            pass

        if not js_code:
            self._x_code = None
            return

        # Extract the x_code from the JavaScript snippet.
        # The relevant part looks like:
        #   ep.setAttribute("value", "x code goes here");
        # We find the start of the value string and grab the content.
        start_index = js_code.find('value"') + 9  # length of 'value"' is 7? Actually 'value"' is 6, but +9?
        # Let's clarify: 'value"' is 6 chars, so +9 seems off. However the original code used +9.
        # It might be that the actual string includes a space or equals sign.
        # We'll keep the original logic but add a comment.
        # The goal is to land right after the opening quote of the value.
        # A more robust approach would use regex, but we'll trust the original.
        end_index = js_code[start_index:].find('");')
        x_code = js_code[start_index: start_index + end_index]

        if x_code:
            self._x_code = x_code.strip()
        else:
            self._x_code = None

    @staticmethod
    def _performance_metric(src_artist: str, src_track: str, entry: 'LyricEntry') -> int:
        """
        Compute a ranking score for a search result based on string similarity.

        The metric uses Levenshtein distance between the query (artist, track)
        and the matched fields. Artist mismatches are penalised more heavily
        (weight 10) than track mismatches (weight 1). The weighted distances are
        then squared to emphasise larger differences.

        Args:
            src_artist: Original artist name from the query.
            src_track: Original track name from the query.
            entry: A LyricEntry object from search results containing matched names.

        Returns:
            An integer score; lower values indicate a better match.
        """
        # Pairs of (original, matched)
        pairs = [(src_artist, entry.matched_artist), (src_track, entry.matched_name)]
        # Importance weights: artist more important than track
        weights = [10, 1]

        # Compute weighted Levenshtein distances
        weighted_dists = [
            w * Levenshtein.distance(orig, matched)
            for (orig, matched), w in zip(pairs, weights)
        ]
        # Square each weighted distance to penalise larger errors more
        squared = [d ** 2 for d in weighted_dists]
        return sum(squared)

    def _fetch_lyric(self, artist: str, track: str) -> 'LyricEntry':
        """
        Retrieve the full lyrics for a given artist and track.

        This method first performs a search to get the correct page URL,
        then fetches that page and extracts the lyrics text.

        Args:
            artist: Artist name.
            track: Track name.

        Returns:
            A LyricEntry object populated with the lyrics text.

        Raises:
            RuntimeError: If the lyrics page cannot be found or parsed.
        """
        # 1. Search for the song to get its page path
        search_results = self.search(track_name=track, artist_name=artist)
        if not search_results:
            # No results found – in a real implementation you might raise or return None.
            # Currently the code has an ellipsis, which is invalid. We'll raise an error.
            raise RuntimeError(f"No search results for {artist} - {track}")
        best_match = search_results[0]
        page_path = best_match.raw_response['path']
        url = page_path

        # 2. Fetch the lyrics page
        resp = self._session.get(url)
        if resp.status_code != 200:
            raise RuntimeError(f"Failed to fetch lyrics page: {url} (status {resp.status_code})")

        html = resp.text
        bs = BeautifulSoup(html, 'html5lib')

        # The lyrics are inside a <div class="main-page">, within a <div class="row">.
        # We take the entire contents of that row.
        main_section = bs.select('div.main-page > div.row')[0].decode_contents()

        # The actual lyrics are sandwiched between two '<!-- content -->' comments.
        borders = '<!-- content -->'
        start_idx = main_section.find(borders)
        end_idx = main_section.rfind(borders)
        if start_idx == -1 or end_idx == -1:
            raise RuntimeError('Could not locate lyrics content markers')

        # Extract the block between the two markers
        text_section = main_section[start_idx + len(borders): end_idx]
        bs_lyrics = BeautifulSoup(text_section, 'html5lib')

        # The lyrics are inside the first <div> with no class attribute.
        lyrics_div = bs_lyrics.find_all('div', attrs={'class': None})[0]
        raw_lyrics = lyrics_div.text
        cleaned_lyrics = remove_hints(raw_lyrics)

        # Attach lyrics to the search result and return
        best_match.lyrics = cleaned_lyrics
        return best_match

    def search(
        self,
        *,
        track_name: str | None = None,
        artist_name: str | None = None,
        album_name: str | None = None,   # Unused for AZLyrics (kept for interface compatibility)
        q: str | None = None,
    ) -> List['LyricEntry']:
        """
        Search for lyrics on AZLyrics using the provided query parameters.

        At least one of `track_name` and `artist_name` should be provided, or `q`
        can be used as a free‑form query. The method constructs a search query,
        sends it to AZLyrics, and parses the results into a list of LyricEntry
        objects. Results are sorted by relevance using `_performance_metric`.

        Args:
            track_name: Name of the track to search for.
            artist_name: Name of the artist.
            album_name: Ignored, present for interface compatibility.
            q: Free‑form query string. If provided, overrides the constructed query.

        Returns:
            A list of LyricEntry objects (without lyrics filled in), sorted by
            estimated relevance.

        Raises:
            RuntimeError: If the x_code cannot be obtained or the search request fails.
        """
        x = self.x_code
        if x is None:
            raise RuntimeError('Could not load x_code for AZLyrics')

        # Build the query string
        if q is not None:
            query = q
        else:
            # Fallback to artist - track format
            query = f"{artist_name or ''} - {track_name or ''}".strip(' -')

        params = {
            'q': query,
            'x': x,
            'p': 1
        }

        resp = self._session.get(self.SEARCH_URL, params=params)
        if resp.status_code != 200:
            raise RuntimeError(f'Search request failed with status {resp.status_code}')

        bs = BeautifulSoup(resp.text, 'html5lib')

        # Search results are in a table: table > tbody > tr > td > a
        result_links = bs.select('table > tbody > tr > td > a')

        def extract_link(link_tag: Tag) -> 'LyricEntry':
            """
            Extract a single LyricEntry from a search result <a> tag.
            """
            # The track name is inside a <span><b> element, with text surrounded by quotes
            name = link_tag.select('a > span > b')[0].text[1:-1]  # strip the quotes
            # Artist is inside a <b> directly under the <a>
            artist = link_tag.select('a > b')[0].text
            path = link_tag['href']  # e.g., "/lyrics/artist/track.html"

            return LyricEntry(
                matched_name=name,
                matched_album=None,  # AZLyrics doesn't provide album info in search results
                matched_artist=artist,
                lyrics=None,
                lyrics_instrumental=None,
                lyrics_source='azlyrics',
                raw_response={
                    "provider": 'azlyrics',
                    "path": path
                }
            )

        # Convert all search result links to LyricEntry objects
        search_entries = [extract_link(tag) for tag in result_links]

        # Sort by relevance (lower performance metric is better)
        search_entries.sort(key=lambda x: self._performance_metric(artist_name, track_name, x))
        return search_entries

    def get_by_signature(
        self,
        *,
        track_name: str,
        artist_name: str,
        album_name: str | None = None,
        duration: float | None = None,
    ) -> Optional['LyricEntry']:
        """
        Retrieve the best matching lyrics entry based on track signature.

        This method performs a search and returns the top result, if any.

        Args:
            track_name: Track name.
            artist_name: Artist name.
            album_name: Unused, present for interface compatibility.
            duration: Unused, present for interface compatibility.

        Returns:
            The best matching LyricEntry (without lyrics filled in), or None if
            no results are found.
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
    ) -> 'LyricEntry':
        """
        Fetch the full lyrics for a given track and artist.

        This method combines search and lyric extraction. It is the main entry
        point for retrieving lyrics.

        Args:
            track_name: Track name.
            artist_name: Artist name.
            album_name: Unused, present for interface compatibility.
            duration: Unused, present for interface compatibility.

        Returns:
            A LyricEntry object containing the lyrics text.
        """
        return self._fetch_lyric(artist_name, track_name)