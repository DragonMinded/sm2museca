import argparse
import datetime
import os
import sys

from typing import Dict, Any, Optional
from xml.dom import minidom  # type: ignore

class Museca:

    @staticmethod
    def __get_notesections(data: bytes) -> Dict[str, Dict[str, str]]:
        lines = data.decode('utf-8').replace('\r', '\n').split('\n')
        lines.append('')

        lineno = 1

        sections = {}  # type: Dict[str, Dict[str, str]]

        # This has to be stateful due to the protocol
        cursection = {}  # type: Dict[str, str]
        section = False
        sectionline = 0
        sectionnames = ['style', 'author', 'difficulty', 'rating']

        for line in lines:
            # See if we should start parsing a notes section
            if line == '#NOTES:':
                if section:
                    raise Exception(
                        'Found expected NOTES section on line {}!'.format(lineno)
                    )
                section = True
                sectionline = 0
                cursection = {}

            # See if we have a valid line in a notes section
            elif line.endswith(':') and len(line) > len(line.strip()):
                if section and sectionline < len(sectionnames):
                    cursection[sectionnames[sectionline]] = line[:-1].strip()
                    sectionline = sectionline + 1

            # See if we ended a section.
            elif section:
                if sectionline < 4:
                    raise Exception(
                        'Didn\'t find enough metadata in section ending on line {}!'.format(lineno)
                    )
                section = False
                sections[cursection['difficulty'].lower()] = cursection

            lineno = lineno + 1

        return sections

    @staticmethod
    def get_metadata(idval: int, data: bytes) -> bytes:
        # Grab notes sections
        notedetails = Museca.__get_notesections(data)

        lines = data.decode('utf-8').replace('\r', '\n').split('\n')
        lines = [line[1:-1] for line in lines if line.startswith('#') and line.endswith(';')]
        lines = [line for line in lines if ':' in line]

        infodict = {}  # type: Dict[str, str]
        for line in lines:
            section, value = line.split(':', 1)
            infodict[section.lower()] = value

        # Parse out BPM
        bpms = []
        for bpm in infodict.get('bpms', '').split(','):
            if '=' not in bpm:
                continue
            time_val, bpm_val = bpm.split('=', 1)
            timeval = float(time_val)
            bpmval = float(bpm_val)
            bpms.append((timeval, bpmval))

        # Grab max and min BPM
        maxbpm = max([bpm for (_, bpm) in bpms])
        minbpm = min([bpm for (_, bpm) in bpms])

        # Create root document
        music_data = minidom.Document()
        mdb = music_data.createElement('mdb')
        music_data.appendChild(mdb)

        def element(parent: Any, name: str, value: Optional[str]=None) -> Any:
            element = music_data.createElement(name)
            parent.appendChild(element)

            if value is not None:
                text = music_data.createTextNode(value)
                element.appendChild(text)

            return element

        # Create a single child with the right music ID
        music = element(mdb, 'music')
        music.setAttribute('id', str(idval))

        # Create info section for metadata
        info = element(music, 'info')

        # Copypasta into info the various data we should have
        element(info, 'label', str(idval))
        element(info, 'title_name', infodict.get('title', ''))
        element(info, 'title_yomigana', infodict.get('title_yomigana', ''))
        element(info, 'artist_name', infodict.get('artist', ''))
        element(info, 'artist_yomigana', infodict.get('artist_yomigana', ''))
        element(info, 'ascii', 'dummy')
        element(info, 'bpm_min', str(int(minbpm * 100))).setAttribute('__type', 'u32')
        element(info, 'bpm_max', str(int(maxbpm * 100))).setAttribute('__type', 'u32')
        element(info, 'distribution_date', datetime.date.strftime(datetime.datetime.now(), "%Y%m%d")).setAttribute('__type', 'u32')  # type: ignore

        # TODO: Figure out what some of these should be
        element(info, 'volume', '75').setAttribute('__type', 'u16')
        element(info, 'bg_no', '0').setAttribute('__type', 'u16')
        element(info, 'genre', '16').setAttribute('__type', 'u8')
        element(info, 'is_fixed', '1').setAttribute('__type', 'u8')
        element(info, 'version', '1').setAttribute('__type', 'u8')
        element(info, 'demo_pri', '-2').setAttribute('__type', 's8')
        element(info, 'world', '0').setAttribute('__type', 'u8')
        element(info, 'tier', '-2').setAttribute('__type', 's8')
        element(info, 'license', infodict.get('license', ''))
        element(info, 'bmlink_phase', '75').setAttribute('__type', 's32')
        element(info, 'inf_ver', '75').setAttribute('__type', 'u8')

        return music_data.toprettyxml(indent="  ", encoding='shift-jis')

def main() -> int:
    parser = argparse.ArgumentParser(description="A utility to convert StepMania-like charts to Museca format.")
    parser.add_argument(
        "file",
        metavar="FILE",
        help=".mu file to convert to Museca format.",
        type=str,
    )
    parser.add_argument(
        "id",
        metavar="ID",
        help="ID to assign this song.",
        type=int,
    )
    parser.add_argument(
        "-d",
        "--directory",
        help="Directory to place files in. Defaults to current directory.",
        default='.',
    )

    args = parser.parse_args()
    root = args.directory
    if root[-1] != '/':
        root = root + '/'
    root = os.path.realpath(root)
    os.makedirs(root, exist_ok=True)

    fp = open(args.file, 'rb')
    data = fp.read()
    fp.close()

    # First, write out a metadata file, that can be copied into music-info.xml
    musicinfo = Museca.get_metadata(args.id, data)
    fp = open(os.path.join(root, 'music-info.xml'), 'wb')
    fp.write(musicinfo)
    fp.close()

    return 0

if __name__ == '__main__':
    sys.exit(main())
