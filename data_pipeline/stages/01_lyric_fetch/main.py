from parsers import *


class DataPipelineContext:
    pass


def main(cxt: DataPipelineContext) -> None:
    a = ChainParser(parser_types=get_all_parsers())

    b = a.get_lyrics(track_name='alligator blood', artist_name='')
    # b = a.search(track_name=input('track: '), artist_name=input('artist: '))
    # print(b or 'Error')
    print(b.lyrics)
    print(b.lyrics_source)

def desc() -> str:
    return "Fetch lyrics for the songs from input.csv file"


# if __name__ == 'main':
main(None)