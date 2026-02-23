# Lyric database server
It is the dedicated server the only's purpose is to parse, cache, search, and return lyrics/ 

## External sources
The lyrics are stored in database (postgres or sqlite). If there are no entry in db, when requesting the lyrics, the system relies on external sources, parses data from them and store in db.
List of sample sources:
- [LRCLIB](https://lrclib.net/)
	- Have free api
- Genius
	- Paid api => We use parsing
- To be continued

## Rest

### 1. Search Lyrics in Local Database

**Retrieve song lyrics from the local database by song name, artist, and optionally album.**

- **Endpoint:** `GET /lyrics`
- **Description:** Searches the local database for songs matching the provided criteria. Returns a list of matching songs with their lyrics.
- **Query Parameters:**
  - `song` (string, required) – The name of the song.
  - `artist` (string, required) – The name of the artist.
  - `album` (string, optional) – The album name (to narrow results).
- **Response:** JSON array of song objects (see [Response Format](#response-format)).

**Example Request:**
```
GET /api/lyrics?song=Imagine&artist=John%20Lennon&album=Imagine
```

**Example Response:**
```json
{
  "data": [
    {
      "id": "123e4567-e89b-12d3-a456-426614174000",
      "song": "Imagine",
      "artist": "John Lennon",
      "album": "Imagine",
      "lyrics": "Imagine there's no heaven...",
      "source": "genius"
    }
  ],
  "total": 1
}
```

---

### 2. Search Lyrics from External Sources

**Fetch lyrics from external APIs by song name, artist, and optionally album.**

- **Endpoint:** `GET /lyrics/external`
- **Description:** Queries third‑party lyrics providers (e.g., Genius, Musixmatch, LRCLIB) for the song. Returns the lyrics found externally (no local storage).
- **Query Parameters:** Same as above (`song`, `artist`, `album` optional).
- **Response:** A single song object (or array if multiple matches) with lyrics and source info.

**Example Request:**
```
GET /api/lyrics/external?song=Bohemian%20Rhapsody&artist=Queen
```

**Example Response:**
```json
{
  "data": [
    {
      "id": null,
      "song": "Bohemian Rhapsody",
      "artist": "Queen",
      "album": "A Night at the Opera",
      "lyrics": "Is this the real life? Is this just fantasy?...",
      "source": "genius"
    }
  ],
  "total": 1
}
```

---

### 3. Get Lyrics by ID

**Retrieve a specific song and its lyrics using its unique identifier.**

- **Endpoint:** `GET /lyrics/{id}`
- **Description:** Returns the song data (including lyrics) for the given ID, which must exist in the local database.
- **Path Parameter:**
  - `id` (string, required) – UUID or unique identifier of the song.
- **Response:** Single song object.

**Example Request:**
```
GET /api/lyrics/123e4567-e89b-12d3-a456-426614174000
```

**Example Response:**
```json
{
  "id": "123e4567-e89b-12d3-a456-426614174000",
  "song": "Imagine",
  "artist": "John Lennon",
  "album": "Imagine",
  "lyrics": "Imagine there's no heaven...",
  "source": "local"
}
```


