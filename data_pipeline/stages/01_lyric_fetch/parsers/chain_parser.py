from __future__ import annotations

from typing import List, Type, Union

from .base import BaseParser
from .types import LyricEntry, SongEntry


def _build_parsers(
    parser_types: List[Type[BaseParser]],
    kwargs: Union[dict, List[dict], None],
) -> List[BaseParser]:
    """Instantiate each parser type with the given kwargs."""
    n = len(parser_types)
    if isinstance(kwargs, list):
        if len(kwargs) != n:
            raise ValueError(
                f"kwargs list length ({len(kwargs)}) must match parser_types length ({n})"
            )
        return [cls(**(kw or {})) for cls, kw in zip(parser_types, kwargs)]
    common = kwargs if isinstance(kwargs, dict) else {}
    return [cls(**common) for cls in parser_types]


class ChainParser(BaseParser):
    """
    Composes multiple parsers in order: tries the first, then the next on failure
    or empty result, and so on. Implements the same interface as a single parser.

    Can be constructed either with pre-built instances or with types + kwargs:

      chain = ChainParser(parsers=[LRCLibParser(), GeniusParser()])

      chain = ChainParser(
          parser_types=[LRCLibParser, GeniusParser],
          kwargs={"timeout": 15},
      )

      chain = ChainParser(
          parser_types=[LRCLibParser, GeniusParser],
          kwargs=[{"timeout": 10}, {}],
      )
    """

    def __init__(
        self,
        parsers: List[BaseParser] | None = None,
        parser_types: List[Type[BaseParser]] | None = None,
        kwargs: Union[dict, List[dict], None] = None,
    ) -> None:
        if parsers is not None:
            if not parsers:
                raise ValueError("ChainParser requires at least one parser")
            self.parsers: List[BaseParser] = list(parsers)
        elif parser_types is not None:
            if not parser_types:
                raise ValueError("ChainParser requires at least one parser type")
            self.parsers = _build_parsers(parser_types, kwargs)
        else:
            raise ValueError(
                "ChainParser requires either 'parsers' (list of instances) "
                "or 'parser_types' (list of classes, optionally with 'kwargs')"
            )

    def search(
        self,
        *,
        track_name: str | None = None,
        artist_name: str | None = None,
        album_name: str | None = None,
        q: str | None = None,
    ) -> List[LyricEntry]:
        """Try each parser in order; return the first non-empty result or []."""
        for parser in self.parsers:
            try:
                results = parser.search(
                    track_name=track_name,
                    artist_name=artist_name,
                    album_name=album_name,
                    q=q,
                )
                if results:
                    return results
            except Exception:
                continue
        return []

    def get_by_signature(
        self,
        *,
        track_name: str,
        artist_name: str,
        album_name: str | None = None,
        duration: float | None = None,
    ) -> LyricEntry | None:
        """Try each parser in order; return the first non-None result or None."""
        for parser in self.parsers:
            try:
                entry = parser.get_by_signature(
                    track_name=track_name,
                    artist_name=artist_name,
                    album_name=album_name,
                    duration=duration,
                )
                if entry is not None:
                    return entry
            except Exception:
                continue
        return None

    def get_lyrics(
        self,
        *,
        track_name: str,
        artist_name: str,
        album_name: str | None = None,
        duration: float | None = None,
    ) -> LyricEntry:
        """Try each parser in order; return the first success or re-raise the last error."""
        last_error: Exception | None = None
        for parser in self.parsers:
            try:
                return parser.get_lyrics(
                    track_name=track_name,
                    artist_name=artist_name,
                    album_name=album_name,
                    duration=duration,
                )
            except Exception as e:
                last_error = e
                continue
        if last_error is not None:
            raise last_error
        raise ValueError(
            f"No parser could resolve lyrics for: {artist_name} - {track_name}"
        )
