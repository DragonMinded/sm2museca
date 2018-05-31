import os
import tempfile

class Constants:
    EVENT_KIND_NOTE = 0
    EVENT_KIND_HOLD = 1
    EVENT_KIND_LARGE_SPINNER = 2
    EVENT_KIND_LARGE_SPINNER_LEFT = 3
    EVENT_KIND_LARGE_SPINNER_RIGHT = 4
    EVENT_KIND_SMALL_SPINNER = 5
    EVENT_KIND_SMALL_SPINNER_LEFT = 6
    EVENT_KIND_SMALL_SPINNER_RIGHT = 7

    EVENT_KIND_MEASURE_MARKER = 11
    EVENT_KIND_BEAT_MARKER = 12

    EVENT_KIND_GRAFICA_SECTION_START = 14
    EVENT_KIND_GRAFICA_SECTION_END = 15


class TempFile:

    def __init__(self, suffix: str='') -> None:
        self.__suffix = suffix

    def __enter__(self) -> str:
        # Workaround for windows.
        self.__tempfile = tempfile.NamedTemporaryFile(
            suffix=self.__suffix,
            delete=False,
        )
        return self.__tempfile.name

    def __exit__(self, *args) -> None:
        os.remove(self.__tempfile.name)


def read_file(name: str) -> bytes:
    fp = open(name, 'rb')
    bv = fp.read()
    fp.close()
    return bv
