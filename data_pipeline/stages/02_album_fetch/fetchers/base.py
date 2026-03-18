from abc import ABC, abstractmethod
from collections.abc import Iterable
from typing import List

from .types import AlbumCover


class BaseFetcher(ABC):
    """Abstract base class for album cover fetchers."""

    @abstractmethod
    def find_cover(self, artist: str, album: str) -> AlbumCover:
        """Find the album cover for a given artist and album name.
        Args:
            artist (str): The name of the artist.
            album (str): The name of the album.
        Returns:
            AlbumCover: An object containing the album cover information.
        """
        pass