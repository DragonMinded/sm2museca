import os
import struct
import subprocess
import tempfile
from typing import Dict, List, Tuple, Optional


class TwoDX:
    def __init__(self, data: Optional[bytes] = None) -> None:
        self.__name = None  # type: Optional[str]
        self.__files = {}  # type: Dict[str, bytes]
        if data is not None:
            self.__parse_file(data)

    def __parse_file(self, data: bytes) -> None:
        # Parse file header
        (name, headerSize, numfiles) = struct.unpack('<16sII', data[0:24])
        self.__name = name.split(b'\x00')[0].decode('ascii')

        if headerSize != (72 + (4 * numfiles)):
            raise Exception('Unrecognized 2dx file header!')

        fileoffsets = struct.unpack('<' + ''.join(['I' for _ in range(numfiles)]), data[72:(72 + (4 * numfiles))])
        fileno = 1

        for offset in fileoffsets:
            (magic, headerSize, wavSize, _, track, _, attenuation, loop) = struct.unpack(
                '<4sIIhhhhi',
                data[offset:(offset+24)],
            )

            if magic != b'2DX9':
                raise Exception('Unrecognized entry in file!')
            if headerSize != 24:
                raise Exception('Unrecognized subheader in file!')

            wavOffset = offset + headerSize
            wavData = data[wavOffset:(wavOffset + wavSize)]

            self.__files['{}_{}.wav'.format(self.__name, fileno)] = wavData
            fileno = fileno + 1

    @property
    def name(self) -> str:
        return self.__name

    def set_name(self, name: str) -> None:
        if len(name) <= 16:
            self.__name = name
        else:
            raise Exception('Name of archive too long!')

    @property
    def filenames(self) -> List[str]:
        return [f for f in self.__files]

    def read_file(self, filename: str) -> bytes:
        return self.__files[filename]

    def write_file(self, filename: str, data: bytes) -> None:
        self.__files[filename] = data

    def get_new_data(self) -> bytes:
        if not self.__files:
            raise Exception('No files to write!')
        if not self.__name:
            raise Exception('2dx archive name not set!')

        name = self.__name.encode('ascii')
        while len(name) < 16:
            name = name + b'\x00'
        filedata = [self.__files[x] for x in self.__files]

        # Header length is also the base offset for the first file
        baseoffset = 72 + (4 * len(filedata))
        data = [struct.pack('<16sII', name, baseoffset, len(filedata)) + (b'\x00' * 48)]

        # Calculate offset this will go to
        for bytedata in filedata:
            # Add where this file will go, then calculate the length
            data.append(struct.pack('<I', baseoffset))
            baseoffset = baseoffset + 24 + len(bytedata)

        # Now output the headers and files
        for bytedata in filedata:
            data.append(struct.pack(
                '<4sIIhhhhi',
                b'2DX9',
                24,
                len(bytedata),
                0x3231,
                -1,
                64,
                1,
                0,
            ))
            data.append(bytedata)

        return b''.join(data)


class ADPCM:

    def __init__(self, filename: str) -> None:
        self.__filename = filename
        self.__data = None

    def __conv_file(self) -> None:
        if self.__data is not None:
            raise Exception('Logic error, re-converting audio file!')
        if not os.path.exists(self.__filename):
            raise Exception('File \'{}\' does not exist!'.format(self.__filename))

        # We must create a temporary file, use ffmpeg to convert the file
        # to MS-ADPCM and then load those bytes in.
        with tempfile.NamedTemporaryFile(suffix='.wav') as temp:
            subprocess.call([
                'ffmpeg',
                '-y',
                '-hide_banner',
                '-nostats',
                '-loglevel',
                'quiet',
                '-i',
                self.__filename,
                '-acodec',
                'adpcm_ms',
                '-ar',
                '44100',
                temp.name,
            ])

            temp.seek(0)
            self.__data = temp.read()

    def get_adpcm_data(self) -> bytes:
        if self.__data is None:
            self.__conv_file()

        return self.__data
