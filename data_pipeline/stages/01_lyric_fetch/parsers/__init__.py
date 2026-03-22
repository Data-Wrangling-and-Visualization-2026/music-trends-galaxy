from .base import BaseParser
from .azlyrics import AZLyricsParser
from .genius import GeniusParser
from .libsrc import LRCLibParser
from .chain_parser import ChainParser

from .types import LyricEntry 

def get_all_parsers() -> list[BaseParser]:
    return [
        LRCLibParser,
        GeniusParser,
        AZLyricsParser
    ]