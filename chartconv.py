import argparse
import datetime
import os
import sys

from typing import Dict, Any, List, Tuple, Optional
from xml.dom import minidom  # type: ignore

class Museca:

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

    @staticmethod
    def get_notes(difficulty: str, data: bytes) -> bytes:
        # Grab info
        infodict = Museca.__get_metadata(data)

        # Grab notes sections
        notedetails = Museca.__get_notesections(data).get(difficulty)
        if notedetails is None:
            return b''

        # Make sure we can parse the final measure
        if notedetails['data']:
            notedetails['data'].append((notedetails['data'][-1][0] + 1, ','))

        # Parse out BPM, convert to milliseconds
        bpms = Museca.__get_bpms(infodict.get('bpms', ''))
        bpms = sorted(
            [(ts * 1000.0, bpm) for (ts, bpm) in bpms],
            key=lambda b: b[0]
        )

        # Given a current time in milliseconds, return the BPM at the start of that
        # measure.
        def get_cur_bpm(cts: float) -> float:
            for (ts, bpm) in bpms:
                if cts >= ts:
                    return bpm
            raise Exception('Can\'t determine BPM!')

        # Parse out the chart, one measure at a time.
        curmeasure = []  # type: List[Tuple[int, str]]
        events = []  # type: List[Dict[str, int]]
        pending_events = []  # type: List[Tuple[int, Dict[str, int]]]

        # The time at the beginning of the measure, in milliseconds
        curtime = float(infodict.get('offset', '0.0')) * 1000.0

        def event(kind: int, lane: int, start: float, end: float) -> Dict[str, int]:
            return {
                'kind': kind,
                'lane': lane,
                'start': int(start),
                'end': int(end),
            }

        def parse_measure(curtime: float, measure: List[Tuple[int, str]]) -> float:
            # First, get the BPM of this measure, and the divisor for the measure.
            bpm = get_cur_bpm(curtime)
            notes_per_measure = len(measure)

            # Measures are 4/4 time, so figure out what one measure costs time-wise
            seconds_per_beat = 60.0/bpm
            seconds_per_measure = seconds_per_beat * 4.0

            # Now, scale so we know how many seconds are taken up per tick in this
            # measure.
            ms_per_note = (seconds_per_measure / notes_per_measure) * 1000.0

            # Also determine standard quarter-note spacing so we can lay out measure markers
            ms_per_marker = (seconds_per_measure / 4) * 1000.0

            # First, lets output the measure markers
            events.append(event(
                Museca.EVENT_KIND_MEASURE_MARKER,
                Museca.EVENT_KIND_MEASURE_MARKER,
                curtime,
                curtime,
            ))
            events.append(event(
                Museca.EVENT_KIND_BEAT_MARKER,
                Museca.EVENT_KIND_BEAT_MARKER,
                curtime + ms_per_marker,
                curtime + ms_per_marker,
            ))
            events.append(event(
                Museca.EVENT_KIND_BEAT_MARKER,
                Museca.EVENT_KIND_BEAT_MARKER,
                curtime + ms_per_marker * 2,
                curtime + ms_per_marker * 2,
            ))
            events.append(event(
                Museca.EVENT_KIND_BEAT_MARKER,
                Museca.EVENT_KIND_BEAT_MARKER,
                curtime + ms_per_marker * 3,
                curtime + ms_per_marker * 3,
            ))

            # Now, lets parse out the notes for each note in the measure.
            for (lineno, measurestring) in measure:
                measuredata = [d.strip() for d in measurestring.split(' ')]
                baddata = [d for d in measuredata if len(d) > 0 and len(d) != 6]
                if len(baddata) > 0:
                    raise Exception('Invalid measure data on line {}!'.format(lineno))

                measuredata = [d for d in measuredata if len(d) == 6]
                for mset in measuredata:
                    for lane in range(len(mset)):
                        val = mset[lane]
                        if val == '0':
                            # No note
                            continue
                        elif val in ['1', 's', 'l', 'r']:
                            # Regular note/spin
                            if lane == 5:
                                raise Exception('Invalid regular note on foot pedal on line {}!'.format(lineno))

                            events.append(event(
                                {
                                    '1': Museca.EVENT_KIND_NOTE,
                                    's': Museca.EVENT_KIND_SMALL_SPINNER,
                                    'l': Museca.EVENT_KIND_SMALL_SPINNER_LEFT,
                                    'r': Museca.EVENT_KIND_SMALL_SPINNER_RIGHT,
                                }[val],
                                lane,
                                curtime,
                                curtime,
                            ))
                        elif val in ['2', 'S', 'L', 'R']:
                            # Hold note/large spin start
                            pending_events.append((
                                lineno,
                                event(
                                    {
                                        '2': Museca.EVENT_KIND_HOLD,
                                        'S': Museca.EVENT_KIND_LARGE_SPINNER,
                                        'L': Museca.EVENT_KIND_LARGE_SPINNER_LEFT,
                                        'R': Museca.EVENT_KIND_LARGE_SPINNER_RIGHT,
                                    }[val],
                                    lane,
                                    curtime,
                                    curtime,
                                )
                            ))
                        elif val == '3':
                            found = False
                            for i in range(len(pending_events)):
                                if (
                                    pending_events[i][1]['kind'] == Museca.EVENT_KIND_HOLD and
                                    pending_events[i][1]['lane'] == lane
                                ):
                                    # Found start, transfer it
                                    pending_events[i][1]['end'] = int(curtime)
                                    events.append(pending_events[i][1])
                                    del pending_events[i]

                                    found = True
                                    break

                            if not found:
                                raise Exception('End hold note with no start hold found on line {}!'.format(lineno))
                        elif val == 'T':
                            found = False
                            for i in range(len(pending_events)):
                                if (
                                    pending_events[i][1]['kind'] in [
                                        Museca.EVENT_KIND_LARGE_SPINNER,
                                        Museca.EVENT_KIND_LARGE_SPINNER_LEFT,
                                        Museca.EVENT_KIND_LARGE_SPINNER_RIGHT,
                                    ] and pending_events[i][1]['lane'] == lane
                                ):
                                    # Found start, transfer it
                                    pending_events[i][1]['end'] = int(curtime)
                                    events.append(pending_events[i][1])
                                    del pending_events[i]

                                    found = True
                                    break

                            if not found:
                                raise Exception('End spin note with no start spin found on line {}!'.format(lineno))
                        else:
                            raise Exception('Unknown note type {} on line {}!'.format(val, lineno))

                # Move ourselves forward past this time.
                curtime = curtime + ms_per_note

            # Finally, update our time
            return curtime

        for (lineno, line) in notedetails['data']:
            if line.strip() == ',':
                # Parse out current measure
                curtime = parse_measure(curtime, curmeasure)
                curmeasure = []
            else:
                curmeasure.append((lineno, line))

        for (lineno, evt) in pending_events:
            raise Exception('Note started on line {} is missing end marker!'.format(lineno))

        # Events can be generated out of order, so lets sort them!
        events = sorted(
            events,
            key=lambda event: event['start'],
        )

        # Write out the chart
        chart = minidom.Document()
        root = chart.createElement('data')
        chart.appendChild(root)

        def element(parent: Any, name: str, value: Optional[str]=None) -> Any:
            element = chart.createElement(name)
            parent.appendChild(element)

            if value is not None:
                text = chart.createTextNode(value)
                element.appendChild(text)

            return element

        # Chart info
        smf_info = element(root, 'smf_info')
        element(smf_info, 'ticks', '480').setAttribute('__type', 's32')

        tempo_info = element(smf_info, 'tempo_info')

        # Copy down BPM changes
        for (timedelta, bpm) in bpms:
            tempo = element(tempo_info, 'tempo')
            element(tempo, 'time', str(int(timedelta * 100))).setAttribute('__type', 's32')
            element(tempo, 'delta_time', '0').setAttribute('__type', 's32')
            element(tempo, 'val', str(int((60.0 / bpm) * 1000000))).setAttribute('__type', 's32')
            element(tempo, 'bpm', str(int(bpm * 100))).setAttribute('__type', 's64')

        # We don't currently support signature changes, so none of that here
        sig_info = element(smf_info, 'sig_info')
        signature = element(sig_info, 'signature')
        element(signature, 'time', '0').setAttribute('__type', 's32')
        element(signature, 'delta_time', '0').setAttribute('__type', 's32')
        element(signature, 'num', '4').setAttribute('__type', 's32')
        element(signature, 'denomi', '4').setAttribute('__type', 's32')

        # Output parsed events
        for parsedevent in events:
            kind = parsedevent['kind']
            lane = parsedevent['lane']

            if kind in [
                Museca.EVENT_KIND_MEASURE_MARKER,
                Museca.EVENT_KIND_BEAT_MARKER,
                Museca.EVENT_KIND_GRAFICA_SECTION_START,
                Museca.EVENT_KIND_GRAFICA_SECTION_END,
            ]:
                # Special case, the lane doesn't matter for these as they're global.
                lane = kind

            if kind in [
                Museca.EVENT_KIND_HOLD,
                Museca.EVENT_KIND_LARGE_SPINNER,
                Museca.EVENT_KIND_LARGE_SPINNER_LEFT,
                Museca.EVENT_KIND_LARGE_SPINNER_RIGHT,
            ]:
                # Special case, holds and spins use 6-10 instead of 0-4. They still
                # use 5 for foot pedal though because that can only be a hold.
                if lane >= 0 and lane <= 4:
                    lane = 6 + lane

            eventnode = element(root, 'event')
            element(eventnode, 'stime_ms', str(parsedevent['start'])).setAttribute('__type', 's64')
            element(eventnode, 'etime_ms', str(parsedevent['end'])).setAttribute('__type', 's64')
            element(eventnode, 'type', str(lane)).setAttribute('__type', 's32')
            element(eventnode, 'kind', str(kind)).setAttribute('__type', 's32')

        # Return the chart data.
        return chart.toprettyxml(indent="  ").encode('ascii')

    @staticmethod
    def __get_notesections(data: bytes) -> Dict[str, Dict[str, Any]]:
        lines = data.decode('utf-8').replace('\r\n', '\n').replace('\r', '\n').split('\n')
        lines.append('')

        # Line number for error reasons
        lineno = 1

        # All finished parsed sections
        sections = {}  # type: Dict[str, Dict[str, Any]]

        # Data we're building up about the current section
        cursection = {}  # type: Dict[str, Any]

        # Whether we're in a section or not.
        section = False

        # The line of the section metadata we're parsing.
        sectionline = 0

        # The names of the section metadata based on the above line.
        sectionnames = ['style', 'author', 'difficulty', 'rating']

        # The line number that started the current section.
        sectionstart = 0

        # The measure data for the current section.
        sectiondata = []  # type: List[Tuple[int, str]]

        for line in lines:
            # See if we should start parsing a notes section
            if line == '#NOTES:':
                if section:
                    raise Exception(
                        'Found unexpected NOTES section on line {} inside existing section starting on line {}!'.format(lineno, sectionstart)
                    )
                section = True
                sectionline = 0
                sectionstart = lineno
                cursection = {}
                sectiondata = []

            # See if we have a valid line in a notes section
            elif line.endswith(':') and len(line) > len(line.strip()):
                if section and sectionline < len(sectionnames):
                    cursection[sectionnames[sectionline]] = line[:-1].strip()
                    sectionline = sectionline + 1

            # See if we ended a section.
            elif line.strip() == ';':
                if not section:
                    raise Exception(
                        'Found spurious end section on line {}!'.format(lineno)
                    )
                if sectionline < 4:
                    raise Exception(
                        'Didn\'t find enough metadata in section starting on line {}!'.format(sectionstart)
                    )

                cursection['data'] = sectiondata
                section = False
                sections[cursection['difficulty'].lower()] = cursection

            # Either measure data or garbage we care nothing about
            elif section:
                sectiondata.append((lineno, line))

            lineno = lineno + 1

        return sections

    @staticmethod
    def __get_metadata(data: bytes) -> Dict[str, str]:
        lines = data.decode('utf-8').replace('\r', '\n').split('\n')
        lines = [line[1:-1] for line in lines if line.startswith('#') and line.endswith(';')]
        lines = [line for line in lines if ':' in line]

        infodict = {}  # type: Dict[str, str]
        for line in lines:
            section, value = line.split(':', 1)
            infodict[section.lower()] = value

        return infodict

    @staticmethod
    def __get_bpms(bpmstr: str) -> List[Tuple[float, float]]:
        bpms = []
        for bpm in bpmstr.split(','):
            if '=' not in bpm:
                continue
            time_val, bpm_val = bpm.split('=', 1)
            timeval = float(time_val)
            bpmval = float(bpm_val)
            bpms.append((timeval, bpmval))

        return bpms

    @staticmethod
    def get_metadata(idval: int, data: bytes) -> bytes:
        # Grab info
        infodict = Museca.__get_metadata(data)

        # Grab notes sections
        notedetails = Museca.__get_notesections(data)

        # Parse out BPM
        bpms = Museca.__get_bpms(infodict.get('bpms', ''))

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
        element(info, 'vmlink_phase', '0').setAttribute('__type', 's32')
        element(info, 'inf_ver', '0').setAttribute('__type', 'u8')

        # Create difficulties section
        difficulty = element(music, 'difficulty')
        for diffval in ['novice', 'advanced', 'exhaust', 'infinite']:
            root = element(difficulty, diffval)
            if diffval != 'infinite':
                details = notedetails.get(diffval, {})
            else:
                detauls = {}  # type: Dict[str, str]

            element(root, 'difnum', details.get('rating', '0')).setAttribute('__type', 'u8')
            element(root, 'illustrator', infodict.get('credit'))
            element(root, 'effected_by', details.get('author'))
            element(root, 'price', '-1').setAttribute('__type', 's32')
            element(root, 'limited', '1' if (diffval == 'infinite' or  details.get('rating', '0') == '0') else '3').setAttribute('__type', 'u8')

        return music_data.toprettyxml(indent="  ", encoding='utf-8').replace(b'utf-8', b'shift-jis')

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

    # Now, write out the chart data
    novice = Museca.get_notes('novice', data)
    fp = open(os.path.join(root, '01_{num:04d}_nov.xml'.format(num=args.id)), 'wb')
    fp.write(novice)
    fp.close()

    # Now, write out the chart data
    advanced = Museca.get_notes('advanced', data)
    fp = open(os.path.join(root, '01_{num:04d}_adv.xml'.format(num=args.id)), 'wb')
    fp.write(advanced)
    fp.close()

    # Now, write out the chart data
    exhaust = Museca.get_notes('exhaust', data)
    fp = open(os.path.join(root, '01_{num:04d}_exh.xml'.format(num=args.id)), 'wb')
    fp.write(exhaust)
    fp.close()

    # Write out miscelaneous files
    fp = open(os.path.join(root, '01_{num:04d}.def'.format(num=args.id)), 'wb')
    fp.write('#define 01_{num:04d}   0\n'.format(num=args.id).encode('ascii'))
    fp.close()
    fp = open(os.path.join(root, '01_{num:04d}_prv.def'.format(num=args.id)), 'wb')
    fp.write('#define 01_{num:04d}_prv   0\n'.format(num=args.id).encode('ascii'))
    fp.close()

    return 0

if __name__ == '__main__':
    sys.exit(main())
