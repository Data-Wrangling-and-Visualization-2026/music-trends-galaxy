from typing import List, Literal
import dataclasses
from PIL import Image


@dataclasses.dataclass
class AlbumSearchResult:
    album_name: str
    artists: List[str]
    api_path: str
    image_path: str
    image_source: str
    found_class: Literal['artist', 'album']
    additional_info: dict

@dataclasses.dataclass
class AlbumCover:
    album_id: str
    album_name: str
    artists: List[str]
    image_path: str
    image_source: str
    image: Image.Image
    found_class: Literal['artist', 'album']
    additional_info: dict