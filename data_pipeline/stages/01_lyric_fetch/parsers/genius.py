import bs4
import requests
import functools as fnt
from urllib.parse import urljoin
from typing import List
from .types import LyricEntry, SongEntry

## utility
def get_text_with_linebreaks(element):
    """
    Extract text from an element, inserting newlines for block-level tags and <br>.
    """
    # Define which tags are block-level (add more as needed)
    block_tags = {'p', 'li', 'ul', 'ol', 'blockquote', 'pre', 'hr'}
    result = []

    for content in element.children:
        if isinstance(content, bs4.NavigableString):
            # It's plain text – add it (strip or not depending on your need)
            text = str(content)
            if text:  # ignore empty strings?
                result.append(text)
        elif isinstance(content, bs4.Tag):
            if content.name == 'br':
                # <br> tag: add a newline
                result.append('\n')
            else:
                # Recurse into the tag
                inner_text = get_text_with_linebreaks(content)
                if inner_text:
                    result.append(inner_text)
                # After a block tag, add a newline
                if content.name in block_tags:
                    result.append('\n')
    return ''.join(result)

def genius_cleanup(text:str) -> str:
    """
    Removes the [...] like annotations in the text
    """
    lines = map(str.strip, text.splitlines())
    lines = filter(lambda x: not(x.startswith('[') and x.endswith(']')), lines)

    return '\n'.join(lines)

@fnt.lru_cache(maxsize=None)
def genius_search_song(artist: str, track: str) -> List['SongEntry']:
    """
    Search for a song on Genius and return a list of matching entries.
    Results are cached to avoid repeated API calls.
    """
    url = 'https://genius.com/api/search/multi'
    query = {
        'q': f'{artist} - {track}',
        'per_page': 5
    }

    try:
        response = requests.get(url, params=query)
        response.raise_for_status()  # Raise HTTPError for bad responses
        data = response.json()
    except (requests.RequestException, ValueError) as e:
        raise RuntimeError(f"Failed to fetch search results: {e}") from e

    # Extract song sections
    sections = data.get('response', {}).get('sections', [])
    song_sections = [s for s in sections if s.get('type') == 'song']

    if not song_sections:
        return []  # No song sections found

    # Collect all song hits
    all_hits = []
    for section in song_sections:
        hits = section.get('hits', [])
        # Each hit must be of type 'song' and contain a 'result'
        all_hits.extend(
            hit['result'] for hit in hits
            if hit.get('type') == 'song' and 'result' in hit
        )

    # Convert to SongEntry objects
    entries = []
    for result in all_hits:
        # Extract only the fields we need
        entry_data = {
            'artist_names': result.get('artist_names', ''),
            'full_title': result.get('full_title', ''),
            'path': result.get('path', '')
        }
        entries.append(SongEntry(
            artis=entry_data['artist_names'],     # Note: parameter name may be 'artist' instead of 'artis'
            name=entry_data['full_title'],
            path=entry_data['path'],
            src='genius'
        ))

    return entries

def genius_get_lyric(artist: str, track: str) -> LyricEntry:
    """
    Fetch the lyrics container for a given artist and track from Genius.
    Returns a BeautifulSoup Tag object representing the lyrics root element.
    """
    base_url = 'https://genius.com/'
    
    # Search for the song (assuming search_song is defined elsewhere)
    entries = genius_search_song(artist, track)
    if not entries:
        raise ValueError(f"No entries found for {artist} - {track}")
    
    entry = entries[0]
    url = urljoin(base_url, entry.path)
    
    # Fetch the lyrics page
    response = requests.get(url)
    if response.status_code != 200:
        raise ConnectionError(f"Cannot load lyrics page (status {response.status_code})")
    
    soup = bs4.BeautifulSoup(response.text, 'html5lib')
    
    # Find the main application div and then the lyrics root
    app_div = soup.find('div', id='application')
    if app_div is None:
        raise LookupError("Could not find application div")
    
    lyrics_root = app_div.find('div', id='lyrics-root')
    if lyrics_root is None:
        # Sometimes lyrics are in a different container; try alternative selectors
        lyrics_root = soup.find('div', {'data-lyrics-container': 'true'})
        if lyrics_root is None:
            raise LookupError("Could not find lyrics container")
    
    # If for some reason we got a ResultSet (list), take the first element
    if isinstance(lyrics_root, bs4.element.ResultSet):
        lyrics_root = lyrics_root[0]

    lyrics_root = lyrics_root.find_all('div', class_='Lyrics__Container-sc-d7157b20-1 Mfmpf')
    for lyric_entry in lyrics_root:
        for trash in lyric_entry.find_all('div', class_='LyricsHeader__Container-sc-2ca6447a-1 cgxMBK'):
            trash.decompose()
    
    text = '\n'.join(get_text_with_linebreaks(i) for i in lyrics_root)
    text = genius_cleanup(text)

    return LyricEntry(name=entry.name, artist=entry.artis, lyrics=text, src='genius')

