import requests
from typing import List, Optional
from PIL import Image
from io import BytesIO
from rapidfuzz.distance import Levenshtein

from .types import AlbumSearchResult, AlbumCover
from .base import BaseFetcher

class GeniusFetcher(BaseFetcher):
    URL = 'https://genius.com/api/search/multi?'
    
    _session: requests.Session
    HEADER = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    def __init__(self):
        self._session = requests.Session()
        self._session.headers.update(self.HEADER)

    @staticmethod
    def _compute_performance_score(src_album: str, src_artist: str, result: AlbumSearchResult) -> float:
        # Compute a performance score based on the Levenshtein distance between the query and the result's album name and artists
        album_score = Levenshtein.normalized_similarity(src_album, result.album_name) * 0.7
        artist_score = max(Levenshtein.normalized_similarity(artist, artist) for artist in result.artists) * 0.3
        
        score = album_score + artist_score
        result.additional_info['performance_score'] = {
            'album_score': album_score,
            'artist_score': artist_score,
            'total_score': score
        }

        return score

    def _search(self, album: str, artist: str) -> List[AlbumSearchResult]:
        query = f"{artist} - {album}"
        params = {'q': query, 'per_page': 5}
        response = self._session.get(self.URL, params=params)
        response.raise_for_status()

        json_data = response.json()
        data = json_data.get('response', {}).get('sections', [])

        def parse_album_section(album_data: dict) -> AlbumSearchResult:
            result = album_data.get('result', {})
            return AlbumSearchResult(
                album_name      =       result.get('full_title', None),
                artists         =       [i.get('name', '') for i in result.get('primary_artists', [])],
                api_path        =       result.get('api_path', None),
                image_path      =       result.get('cover_art_thumbnail_url', None),
                image_source    =       'genius',
                additional_info =       {}
            )
        
        def find_section(sections: List[dict], section_name: str) -> Optional[dict]:
            prefilter = lambda x: x.get('type', '') == 'album'
            for section in sections:
                if section.get('type') == section_name:
                    output = section.get('hits', None)
                    return None if output is None else list(filter(prefilter, output))
            return None

        section = find_section(data, 'album') or find_section(data, 'top_hit')
        if section is None:
            return []
        
        found_sections  = map(parse_album_section, section)
        found_sections = sorted(found_sections, key=lambda x: self._compute_performance_score(album, artist, x), reverse=True)
        return found_sections
        
    def _fetch_image(self, image_url: str) -> Image.Image:
        response = self._session.get(image_url)
        response.raise_for_status()
        return Image.open(BytesIO(response.content))
    
    def find_cover(self, artist: str, album: str) -> AlbumCover:
        search_results = self._search(artist, album)
        if not search_results:
            raise RuntimeError(f"No results found for query: {artist} - {album}")
        
        best_result = search_results[0]
        image = self._fetch_image(best_result.image_path)
        
        return AlbumCover(
            album_id       =       None,
            album_name     =       best_result.album_name,
            artists        =       best_result.artists,
            image_path     =       best_result.image_path,
            image_source   =       best_result.image_source,
            image          =       image,
            additional_info =      best_result.additional_info
        )