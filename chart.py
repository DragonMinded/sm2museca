import sys

from typing import Dict, Any, List, Tuple, Optional

from misc import Constants


class Chart:

    def __init__(self, data: bytes) -> None:
        self.metadata = self.__get_metadata(data)  # type: Dict[str, str]
        self.notes = self.__get_notesections(data)  # type: Dict[str, Dict[str, Any]]

        # Calculate BPM info up front instead of every time it is requested
        bpms = []
        for bpm in self.metadata.get('bpms', '').split(','):
            if '=' not in bpm:
                continue
            time_val, bpm_val = bpm.split('=', 1)
            timeval = float(time_val)
            bpmval = float(bpm_val)
            bpms.append((timeval, bpmval))
        self.bpms = bpms  # type: List[Tuple[float, float]]

        # Calculate events up front
        self.events = {}  # type: Dict[str, List[Dict[str, int]]]
        for difficulty in ['novice', 'advanced', 'exhaust']:
            if difficulty not in self.notes:
                continue
            self.events[difficulty] = self.__get_events(difficulty, self.notes[difficulty])

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
    def __get_notesections(data: bytes) -> Dict[str, Dict[str, Any]]:
        lines = data.decode('utf-8').replace('\r\n', '\n').replace('\r', '\n').split('\n')
        lines.append('')

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

        # Line number for error reasons
        for lineno, line in enumerate(lines, start=1):
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

        return sections

    def __get_events(self, difficulty: str, notedetails: Dict[str, Any]) -> Optional[List[Dict[str, int]]]:
        # Make sure we can parse the final measure
        if notedetails['data']:
            notedetails['data'].append((notedetails['data'][-1][0] + 1, ','))

        # Parse out BPM, convert to milliseconds
        bpms = sorted(
            [(ts * 1000.0, bpm) for (ts, bpm) in self.bpms],
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
        grafica_toggles = 0

        # The time at the beginning of the measure, in milliseconds
        curtime = float(self.metadata.get('offset', '0.0')) * 1000.0

        def event(kind: int, lane: int, start: float, end: float) -> Dict[str, int]:
            return {
                'kind': kind,
                'lane': lane,
                'start': int(start),
                'end': int(end),
            }

        def parse_measure(curtime: float, measure: List[Tuple[int, str]]) -> float:
            # Allow ourselves to reference the per-chart grafica state.
            nonlocal grafica_toggles

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
                Constants.EVENT_KIND_MEASURE_MARKER,
                Constants.EVENT_KIND_MEASURE_MARKER,
                curtime,
                curtime,
            ))
            events.append(event(
                Constants.EVENT_KIND_BEAT_MARKER,
                Constants.EVENT_KIND_BEAT_MARKER,
                curtime + ms_per_marker,
                curtime + ms_per_marker,
            ))
            events.append(event(
                Constants.EVENT_KIND_BEAT_MARKER,
                Constants.EVENT_KIND_BEAT_MARKER,
                curtime + ms_per_marker * 2,
                curtime + ms_per_marker * 2,
            ))
            events.append(event(
                Constants.EVENT_KIND_BEAT_MARKER,
                Constants.EVENT_KIND_BEAT_MARKER,
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
                seen_grafica = False
                for mset in measuredata:
                    for lane in range(len(mset)):
                        val = mset[lane]
                        if val == '0':
                            # No note
                            continue
                        elif val in ['1', 's', 'l', 'r']:
                            # Regular note/spin
                            if lane == 5:
                                raise Exception('Invalid regular note for foot pedal on line {}!'.format(lineno))

                            events.append(event(
                                {
                                    '1': Constants.EVENT_KIND_NOTE,
                                    's': Constants.EVENT_KIND_SMALL_SPINNER,
                                    'l': Constants.EVENT_KIND_SMALL_SPINNER_LEFT,
                                    'r': Constants.EVENT_KIND_SMALL_SPINNER_RIGHT,
                                }[val],
                                lane,
                                curtime,
                                curtime,
                            ))
                        elif val in ['2', 'S', 'L', 'R']:
                            # Hold note/large spin start
                            if lane == 5 and val != '2':
                                raise Exception('Invalid spin note for foot pedal on line {}!'.format(lineno))

                            # Regular note/spin
                            pending_events.append((
                                lineno,
                                event(
                                    {
                                        '2': Constants.EVENT_KIND_HOLD,
                                        'S': Constants.EVENT_KIND_LARGE_SPINNER,
                                        'L': Constants.EVENT_KIND_LARGE_SPINNER_LEFT,
                                        'R': Constants.EVENT_KIND_LARGE_SPINNER_RIGHT,
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
                                    pending_events[i][1]['kind'] == Constants.EVENT_KIND_HOLD and
                                    pending_events[i][1]['lane'] == lane
                                ):
                                    # Found start, transfer it
                                    pending_events[i][1]['end'] = int(curtime)
                                    events.append(pending_events[i][1])
                                    del pending_events[i]

                                    found = True
                                    break

                            if not found:
                                raise Exception('End hold note with no start hold found for lane {} on line {}!'.format(lane + 1, lineno))
                        elif val == 'T':
                            found = False
                            for i in range(len(pending_events)):
                                if (
                                    pending_events[i][1]['kind'] in [
                                        Constants.EVENT_KIND_LARGE_SPINNER,
                                        Constants.EVENT_KIND_LARGE_SPINNER_LEFT,
                                        Constants.EVENT_KIND_LARGE_SPINNER_RIGHT,
                                    ] and pending_events[i][1]['lane'] == lane
                                ):
                                    # Found start, transfer it
                                    pending_events[i][1]['end'] = int(curtime)
                                    events.append(pending_events[i][1])
                                    del pending_events[i]

                                    found = True
                                    break

                            if not found:
                                raise Exception('End spin note with no start spin found for lane {} on line {}!'.format(lane + 1, lineno))
                        elif val == 'G':
                            if seen_grafica:
                                raise Exception('Multiple grafica start/end notes on line {}!'.format(lineno))
                            if grafica_toggles >= 6:
                                raise Exception('No more than three grafica sections are allowed, tried to add a 4th on line {}!'.format(lineno))
                            if (grafica_toggles % 2) == 0:
                                # Start event
                                events.append(event(
                                    Constants.EVENT_KIND_GRAFICA_SECTION_START,
                                    Constants.EVENT_KIND_GRAFICA_SECTION_START,
                                    curtime,
                                    curtime,
                                ))
                            else:
                                # End event
                                events.append(event(
                                    Constants.EVENT_KIND_GRAFICA_SECTION_END,
                                    Constants.EVENT_KIND_GRAFICA_SECTION_END,
                                    curtime,
                                    curtime,
                                ))

                            grafica_toggles = grafica_toggles + 1
                            seen_grafica = True

                        else:
                            raise Exception('Unknown note type {} for lane {} on line {}!'.format(val, lane + 1, lineno))

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
            raise Exception('Note beginning on line {} for lane {} is missing end marker!'.format(lineno, evt['lane'] + 1))

        if grafica_toggles < 6:
            print('WARNING: Did not specify all three grafica sections for {} difficulty!'.format(difficulty), file=sys.stderr)

        # Events can be generated out of order, so lets sort them!
        events = sorted(
            events,
            key=lambda event: event['start'],
        )

        return events
