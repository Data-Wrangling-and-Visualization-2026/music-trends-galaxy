from typing import List
import dataclasses
from PIL import Image


@dataclasses.dataclass
class AlbumSearchResult:
    album_name: str
    artists: List[str]
    api_path: str
    image_path: str
    image_source: str
    additional_info: dict

@dataclasses.dataclass
class AlbumCover:
    album_id: str
    album_name: str
    artists: List[str]
    image_path: str
    image_source: str
    image: Image.Image
    additional_info: dict