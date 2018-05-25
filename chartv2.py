import argparse
import datetime
import os
import sys

from typing import Dict, Any, List, Tuple, Optional
from xml.dom import minidom  # type: ignore

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

    EVENT_CATEGORY_LARGE_SPINNERS = [EVENT_KIND_LARGE_SPINNER,
                                     EVENT_KIND_LARGE_SPINNER_LEFT,
                                     EVENT_KIND_LARGE_SPINNER_RIGHT]

    # CONSTANTS FOR 16-LANE FORMAT
    # (these may not all get used)
    SM_LANE_PEDAL = 0
    SM_LANE_1  = 1
    SM_LANE_2  = 2
    SM_LANE_3  = 3
    SM_LANE_4  = 4
    SM_LANE_5  = 5
    SM_LANE_1L = 6
    SM_LANE_2L = 7
    SM_LANE_3L = 8
    SM_LANE_4L = 9
    SM_LANE_5L = 10
    SM_LANE_1R = 11
    SM_LANE_2R = 12
    SM_LANE_3R = 13
    SM_LANE_4R = 14
    SM_LANE_5R = 15

    # STEPMANIA LANE LIST (basically the same as [0,15])
    # used for checking line length, potentially other things
    SM_LANES = [SM_LANE_PEDAL,
                SM_LANE_1, SM_LANE_2, SM_LANE_3, SM_LANE_4, SM_LANE_5,
                SM_LANE_1L, SM_LANE_2L, SM_LANE_3L, SM_LANE_4L, SM_LANE_5L,
                SM_LANE_1R, SM_LANE_2R, SM_LANE_3R, SM_LANE_4R, SM_LANE_5R]

    # STEPMANIA NOTE TYPES
    # - only taps, hold starts, hold ends, and mines are in the spec
    SM_NOTE_NONE = '0'
    SM_NOTE_TAP = '1'
    SM_NOTE_HOLD_START = '2'
    SM_NOTE_HOLD_END = '3'
    SM_NOTE_MINE = 'M'
    SM_NOTES = [SM_NOTE_NONE, SM_NOTE_TAP, SM_NOTE_HOLD_START, SM_NOTE_HOLD_END, SM_NOTE_MINE]
    SM_ACTUAL_NOTES = [SM_NOTE_TAP, SM_NOTE_HOLD_START, SM_NOTE_HOLD_END, SM_NOTE_MINE]

    ## CHANNELS ##
    # - interpret taps and holds in CH1 as normal
    # - interpret taps in CH2 or CH3 as spins or storms
    SM_CH1 = [SM_LANE_1, SM_LANE_2, SM_LANE_3, SM_LANE_4, SM_LANE_5]
    SM_CH2 = [SM_LANE_1L, SM_LANE_2L, SM_LANE_3L, SM_LANE_4L, SM_LANE_5L]
    SM_CH3 = [SM_LANE_1R, SM_LANE_2R, SM_LANE_3R, SM_LANE_4R, SM_LANE_5R]
    SM_CHS = [SM_CH1, SM_CH2, SM_CH3]

    ## MUSECA LANES ##
    # - this is where the player should see them in-game
    # - if a mine is in any of these, end a storm object
    MSC_LANE_1 = [SM_LANE_1, SM_LANE_1L, SM_LANE_1R]
    MSC_LANE_2 = [SM_LANE_2, SM_LANE_2L, SM_LANE_2R]
    MSC_LANE_3 = [SM_LANE_3, SM_LANE_3L, SM_LANE_3R]
    MSC_LANE_4 = [SM_LANE_4, SM_LANE_4L, SM_LANE_4R]
    MSC_LANE_5 = [SM_LANE_5, SM_LANE_5L, SM_LANE_5R]
    MSC_LANES = [MSC_LANE_1, MSC_LANE_2, MSC_LANE_3, MSC_LANE_4, MSC_LANE_5, [SM_LANE_PEDAL]]

    ### SPIN LANES ###
    # - if a tap is in both entries, make a non-directional spin
    # - if a hold start is in either entry, start a storm object
    MSC_SPIN_1 = [SM_LANE_1L, SM_LANE_1R]
    MSC_SPIN_2 = [SM_LANE_2L, SM_LANE_2R]
    MSC_SPIN_3 = [SM_LANE_3L, SM_LANE_3R]
    MSC_SPIN_4 = [SM_LANE_4L, SM_LANE_4R]
    MSC_SPIN_5 = [SM_LANE_5L, SM_LANE_5R]
    MSC_SPINS = [MSC_SPIN_1, MSC_SPIN_2, MSC_SPIN_3, MSC_SPIN_4, MSC_SPIN_5]

    ### GRAFICA SECTIONS ###
    # - there should one of each of these (in order!) in the #LABELS section
    GRAFICA_LABELS = ['GRAFICA_1_START', 'GRAFICA_1_END',
                      'GRAFICA_2_START', 'GRAFICA_2_END',
                      'GRAFICA_3_START', 'GRAFICA_3_END']

    ### ALTERNATIVE STORM END EVENTS (as labels) ###
    # - for cases where all 3 channels are currently in use
    # - that is to say: storm ending at the same time as a non-directional spin at the end (or start!) of a hold
    # - TODO: this should be parsed per-chart, which requires support
    #STORM_LABELS = ['STORM_END_LANE_1', 'STORM_END_LANE_2', 'STORM_END_LANE_3', 'STORM_END_LANE_4', 'STORM_END_LANE_5']

# This works similarly to the original sm2museca chart class, except for the part
# where it doesn't. This uses a custom game mode with a 16-lane game type,
# allowing for easier graphical editing of charts, wtih a hopefully easier
# conversion process, without breaking the .sm format while still supporting
# most of the special things that make Museca charts Museca charts.
# (read: simultaneous events)
class Chartv2:

    def __init__(self, data: bytes) -> None:
        self.metadata = self.__get_metadata(data)
        self.notes = self.__get_notesections(data)
        self.events = {}  # type: Dict[str, List[Dict[str, int]]]
        
        if not self.metadata.get('bpms', {}):
            self.metadata['bpms'] = self.notes.get('bpms', {})
        if not self.metadata.get('labels', {}):
            self.metadata['labels'] = self.notes.get('labels', {})
        
        for difficulty in ['easy', 'medium', 'hard']:
            if difficulty not in self.notes:
                continue
            self.events[difficulty] = self.__get_events(difficulty, self.notes[difficulty])

    # TODO: assuming 4/4 all the way for now, revisit this when adding timesig support!
    def beats_to_ms(self, target_beat: float) -> int:
        def __single_section_ms(a: float, b: float) -> float:
            return a / b * 60 * 1000

        if len(self.bpms) == 1:
            return int(__single_section_ms(target_beat, float(self.bpms[0][1])))
        elif len(self.bpms) > 1:
            total_ms = 0

            # target beat is within first BPM section
            if target_beat <= self.bpms[1][0]:
                total_ms = __single_section_ms(target_beat, float(self.bpms[0][1]))
            else:
                delta = 0
                beats_to_calc = 0
                (prev_beat, prev_bpm) = self.bpms[0]

                for i, (cur_beat, cur_bpm) in enumerate(self.bpms[1:], start=1):
                    if cur_beat <= target_beat:
                        beats_to_calc = min(cur_beat, target_beat) - prev_beat
                    else:
                        break

                    delta = __single_section_ms(beats_to_calc, float(prev_bpm))
                    total_ms += delta

                    # we've gone past the end, and must keep counting
                    if i == len(self.bpms[1:]) and target_beat > cur_beat:
                        total_ms += __single_section_ms((target_beat - cur_beat), float(cur_bpm))

                    prev_beat = cur_beat
                    prev_bpm = cur_bpm

            return int(total_ms) + int(float(self.metadata.get('offset', '0.0')) * 1000.0)

    def __get_metadata(self, data: bytes) -> Dict[str, str]:
        lines = data.decode('utf-8').replace('\r', '\n').split('\n')
        lines = [line[1:-1] for line in lines if line.startswith('#') and line.endswith(';')]
        lines = [line for line in lines if ':' in line]

        infodict = {}  # type: Dict[str, str]
        for line in lines:
            section, value = line.split(':', 1)

            if not (infodict.get('credit') and section == 'CREDIT'): # ignore subsequent #CREDIT tags
                infodict[section.lower()] = value

        return infodict

    def __get_notesections(self, data: bytes) -> Dict[str, Dict[str, Any]]:
        def get_single_line_tag_val(line: str) -> str:
            return line.strip().split(':')[1][:-1]
        def get_tag_val_pair(line: str) -> Dict[str, Dict[str, Any]]:
            return line.strip()[:-1].split('=', 1)

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

        # #NOTEDATA
        notedata_section = False

        # Whether we're in the #NOTES section which contains the actual measures
        notes_section = False

        # #BPMS
        bpms_section = False
        
        # #LABELS
        labels_section = False

        # Whether this section is actually a section we can safely ignore
        ignorable_section = False

        # The names of the section metadata based on the above line.
        sectionnames = ['style', 'author', 'difficulty', 'rating']

        # The line number that started the current section.
        sectionstart = 0

        # The measure data for the current section.
        sectiondata = []  # type: List[Tuple[int, str]]

        for line in lines:
            all_sections = ['#BPMS', '#LABELS', '#BGCHANGES', '#NOTEDATA', '#NOTES']

            # ignore sections that start with these
            other_sections = ['#BGCHANGES']
            for ignore_section in other_sections:
                if line.startswith(ignore_section):
                    print('ignoring', ignore_section)
                    section = True
                    ignorable_section = True
                    cursection = {}
                    sectiondata = []
                    other_sections.remove(ignore_section)

            # See if we should start parsing a notedata section (metadata + notes)
            if line.strip() == '#NOTEDATA:;':
                print("beginning #NOTEDATA @", lineno)
                if section:
                    raise Exception(
                        'Found unexpected NOTEDATA section on line {} inside existing section starting on line {}!'.format(lineno, sectionstart)
                    )
                section = True
                notedata_section = True
                sectionstart = lineno
                cursection = {}
                sectiondata = []

            elif line.strip().startswith('#BPMS'):
                print("beginning #BPMS @", lineno)
                if section and bpms_section:
                    raise Exception(
                        'Found unexpected BPMS section on line {} inside existing section starting on line {}!'.format(lineno, sectionstart)
                    )
                section = True
                bpms_section = True
                sectionstart = lineno
                cursection = {}
                sectiondata = []

            elif line.strip().startswith('#LABELS'):
                print("beginning #LABELS @", lineno)
                if section and labels_section:
                    raise Exception(
                        'Found unexpected LABELS section on line {} inside existing section starting on line {}!'.format(lineno, sectionstart)
                    )
                section = True
                labels_section = True
                sectionstart = lineno
                cursection = {}
                sectiondata = []

            # currently in a section, building metadata
            if section and not ignorable_section:
                # Either measure data or garbage we care nothing about
                # Filter out some garbage at least
                if notes_section and \
                   not line.strip().startswith('//') and \
                   not line.strip().startswith(';'):
                    sectiondata.append((lineno, line))
                # We're a little less picky about #BPMS and #LABELS
                elif bpms_section or labels_section:
                    # except for the very first one
                    if lineno == sectionstart:
                        sectiondata.append((lineno, get_single_line_tag_val(line)))
                    else:
                        sectiondata.append((lineno, line.strip()[:-1]))

                # abort parsing this section if it's not for museca
                if line.strip().startswith('#STEPSTYPE'):
                    cursection['style'] = get_single_line_tag_val(line)
                if line.strip().startswith('#DIFFICULTY'):
                    cursection['difficulty'] = get_single_line_tag_val(line)
                if line.strip().startswith('#METER'):
                    cursection['rating'] = get_single_line_tag_val(line)
                if line.strip().startswith('#CREDIT'):
                    # #CREDIT inside of a #NOTEDATA section maps to 'author'/'effected_by'
                    # The top-level #CREDIT is used for 'illustrator'!
                    cursection['author'] = get_single_line_tag_val(line)
                if line.strip().startswith('#NOTES'):
                    print("beginning #NOTES @", lineno, cursection)
                    notes_section = True
                # # chart-specific #BPMS
                # if line.strip().startswith('#BPMS'):
                #     print("beginning #BPMS (chart-level) @", lineno, cursection)
                #     bpms_section = True
                # # chart-specific #LABELS
                # if line.strip().startswith('#BPMS'):
                #     print("beginning #LABELS (chart-level) @", lineno, cursection)
                #     labels_section = True

            # See if we ended a section.
            if line.strip() == ';':
                if not section:
                    raise Exception(
                        'Found spurious end section on line {}!'.format(lineno)
                    )
                else:
                    print("ending section @", lineno, cursection)
                    section = False
                    ignorable_section = False
                    if notes_section:
                        notedata_section = False
                        notes_section = False
                        cursection['data'] = sectiondata
                        if cursection.get('difficulty'):
                            sections[cursection['difficulty'].lower()] = cursection
            elif (bpms_section or labels_section) and line.strip().endswith(';'):
                if not section and (bpms_section or labels_section):
                    raise Exception(
                        'Found spurious end section on line {}!'.format(lineno)
                    )
                else:
                    section = False
                    ignorable_section = False
                    if bpms_section or labels_section:
                        cursection = sectiondata
                        print("ending section @", lineno, cursection)

                        if bpms_section:
                            bpms_section = False
                            sections['bpms'] = cursection
                        elif labels_section:
                            labels_section = False
                            sections['labels'] = cursection

            lineno = lineno + 1

        return sections

    def __get_events(self, difficulty: str, notedetails: Dict[str, Any]) -> Optional[List[Dict[str, int]]]:
        # Make sure we can parse the final measure
        if notedetails['data']:
            notedetails['data'].append((notedetails['data'][-1][0] + 1, ','))

        # Parse out BPM, convert to milliseconds
        bpms = sorted(
            [(self.beats_to_ms(beat), beat, bpm) for (beat, bpm) in self.bpms],
            key=lambda b: b[0]
        )

        # TODO: parse labels, we kinda need those for grafica sections again
        # Parse out labels, convert to milliseconds
        labels = sorted(
            [(self.beats_to_ms(beat), beat, label) for (beat, label) in self.labels],
            key=lambda l: l[0]
        )

        # Given a current time in milliseconds, return the BPM at the start of that
        # measure.
        def get_cur_bpm(cts: float) -> float:
            for (ts, beat, bpm) in bpms:
                if cts >= ts:
                    return bpm
            raise Exception('Can\'t determine BPM!')

        # Parse out the chart, one measure at a time.
        curmeasure = []  # type: List[Tuple[int, str]]
        events = []  # type: List[Dict[str, int]]
        pending_events = []  # type: List[Tuple[int, Dict[str, int]]]

        # The time at the beginning of the measure, in milliseconds
        curtime = float(self.metadata.get('offset', '0.0')) * 1000.0

        def event(kind: int, lane: int, start: float, end: float) -> Dict[str, int]:
            return {
                'kind': kind,
                'lane': lane,
                'start': int(start),
                'end': int(end),
            }

        # read (sorted) labels list and pick out relevant GRAFICA_ entries
        def parse_grafica():
            relevant_labels = [l for l in labels if l[2].startswith('GRAFICA_')]
            if len(relevant_labels) < 6:
                raise Exception('Not enough GRAFICA_ items found in #LABELS, need 6!');
            for i, (time, beat, label) in enumerate(relevant_labels):
                if label != Constants.GRAFICA_LABELS[i]:
                    raise Exception(
                        'Unexpected {} label found in #LABELS, was expecting {}.'.format(label, Constants.GRAFICA_LABELS[i])
                    )
                else:
                    if i % 2 == 0:
                        event_type = Constants.EVENT_KIND_GRAFICA_SECTION_START
                    else:
                        event_type = Constants.EVENT_KIND_GRAFICA_SECTION_END

                    events.append(event(
                        event_type,
                        event_type,
                        time,
                        time
                    ))

        parse_grafica()

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
                mset = measurestring.strip()
                if len(mset) > 0 and len(mset) != len(Constants.SM_LANES):
                    raise Exception('Invalid measure data on line {}!'.format(lineno))

                ## TRULY WHERE IT BEGINS ##
                ## ...and also truly where it needs to be refactored ##
                for msc_lane, sm_lanes in enumerate(Constants.MSC_LANES):
                    # used for event pushes at the very end of the loop
                    event_type = None

                    # hold is starting, push to pending_events instead
                    is_pending = False

                    # hold is ending, check pending_events and push an event
                    resolving_pending = False

                    # if a mine is found, ignore mines anywhere else in this channel
                    storm_ended = False

                    # note data for this channel: ['1', '0', '0']
                    # (or just a single ['0'] for pedal lane)
                    note_data = [mset[x] for x in sm_lanes]

                    # normal lane lookups across all channels
                    if msc_lane < 5:
                        # check mines first for a storm end
                        if Constants.SM_NOTE_MINE in note_data and not storm_ended:
                            found = False
                            for i in range(len(pending_events)):
                                if (
                                    pending_events[i][1]['kind'] in Constants.EVENT_CATEGORY_LARGE_SPINNERS and pending_events[i][1]['lane'] == msc_lane
                                ):
                                    # Found start, transfer it
                                    pending_events[i][1]['end'] = int(curtime)
                                    events.append(pending_events[i][1])
                                    del pending_events[i]
                                    storm_ended = True

                                    found = True
                                    break

                            if not found:
                                raise Exception('End spin note with no start spin found for lane {} on line {}!'.format(msc_lane, lineno))

                        # normal note/spin processing
                        tap = note_data[0]
                        spins = note_data[1:]

                        # normal notes are straightforward
                        if tap == Constants.SM_NOTE_TAP:
                            event_type = Constants.EVENT_KIND_NOTE
                            events.append(event(
                                event_type,
                                msc_lane,
                                curtime,
                                curtime,
                            ))
                        elif tap == Constants.SM_NOTE_HOLD_START:
                            event_type = Constants.EVENT_KIND_HOLD
                            is_pending = True
                            pending_events.append((
                                lineno,
                                event(
                                    event_type,
                                    msc_lane,
                                    curtime,
                                    curtime,
                                )
                            ))
                        elif tap == Constants.SM_NOTE_HOLD_END:
                            resolving_pending = True
                            found = False
                            for i in range(len(pending_events)):
                                if (
                                    pending_events[i][1]['kind'] == Constants.EVENT_KIND_HOLD and
                                    pending_events[i][1]['lane'] == msc_lane
                                ):
                                    # Found start, transfer it
                                    pending_events[i][1]['end'] = int(curtime)
                                    events.append(pending_events[i][1])
                                    del pending_events[i]

                                    found = True
                                    break

                            if not found:
                                raise Exception('End hold note with no start hold found for lane {} on line {}!'.format(msc_lane, lineno))
                        elif tap not in Constants.SM_NOTES:
                            raise Exception('Unknown normal note type {} for lane {} on line {}!'.format(tap, msc_lane, lineno))

                        # both spin lanes have a tap/hold-start, non-directional spin detected
                        if all([(x in [Constants.SM_NOTE_TAP, Constants.SM_NOTE_HOLD_START]) for x in spins]):
                            if Constants.SM_NOTE_HOLD_START in spins:
                                # NOTE: we actually don't care about hold ends in the spin channels at all
                                # but this is still marked is_pending until a mine ends it
                                event_type = Constants.EVENT_KIND_LARGE_SPINNER
                                is_pending = True
                                pending_events.append((
                                lineno,
                                event(
                                        event_type,
                                        msc_lane,
                                        curtime,
                                        curtime,
                                    )
                                ))
                            else: # both spin items are taps
                                event_type = Constants.EVENT_KIND_SMALL_SPINNER
                                events.append(event(
                                    event_type,
                                    msc_lane,
                                    curtime,
                                    curtime,
                                ))
                        else:
                            invalid_note_found = False
                            if spins[0] != Constants.SM_NOTE_NONE: # spin left
                                if spins[0] == Constants.SM_NOTE_TAP:
                                    event_type = Constants.EVENT_KIND_SMALL_SPINNER_LEFT
                                    events.append(event(
                                        event_type,
                                        msc_lane,
                                        curtime,
                                        curtime,
                                    ))
                                elif spins[0] == Constants.SM_NOTE_HOLD_START:
                                    event_type = Constants.EVENT_KIND_LARGE_SPINNER_LEFT
                                    is_pending = True
                                    pending_events.append((
                                        lineno,
                                        event(
                                            event_type,
                                            msc_lane,
                                            curtime,
                                            curtime,
                                        )
                                    ))
                                elif spins[0] not in Constants.SM_NOTES:
                                    invalid_note_found = True
                            if spins[1] != Constants.SM_NOTE_NONE: # spin right
                                if spins[1] == Constants.SM_NOTE_TAP:
                                    event_type = Constants.EVENT_KIND_SMALL_SPINNER_RIGHT
                                    events.append(event(
                                        event_type,
                                        msc_lane,
                                        curtime,
                                        curtime,
                                    ))
                                elif spins[1] == Constants.SM_NOTE_HOLD_START:
                                    event_type = Constants.EVENT_KIND_LARGE_SPINNER_RIGHT
                                    is_pending = True
                                    pending_events.append((
                                        lineno,
                                        event(
                                            event_type,
                                            msc_lane,
                                            curtime,
                                            curtime,
                                        )
                                    ))
                                elif spins[1] not in Constants.SM_NOTES:
                                    invalid_note_found = True

                            if invalid_note_found:
                                raise Exception('Unknown spin note type {} for lane {} on line {}!'.format(spins, msc_lane, lineno))

                    # pedal lane is the last index in this list,
                    # only accepts hold events
                    elif msc_lane == 5:
                        if note_data[0] == Constants.SM_NOTE_HOLD_START:   # pedal start
                            event_type = Constants.EVENT_KIND_HOLD
                            is_pending = True
                            pending_events.append((
                                lineno,
                                event(
                                    event_type,
                                    msc_lane,
                                    curtime,
                                    curtime,
                                )
                            ))
                        elif note_data[0] == Constants.SM_NOTE_HOLD_END: # pedal end
                            resolving_pending = True
                            found = False
                            for i in range(len(pending_events)):
                                if (
                                    pending_events[i][1]['kind'] == Constants.EVENT_KIND_HOLD and
                                    pending_events[i][1]['lane'] == msc_lane
                                ):
                                    # Found start, transfer it
                                    pending_events[i][1]['end'] = int(curtime)
                                    events.append(pending_events[i][1])
                                    del pending_events[i]

                                    found = True
                                    break

                            if not found:
                                raise Exception('End hold note with no start hold found for lane {} on line {}!'.format(msc_lane, lineno))
                        elif note_data[0] in [Constants.SM_NOTE_TAP, Constants.SM_NOTE_MINE]:
                            raise Exception('Invalid note type {} for foot pedal on line {}!'.format(note_data[0], lineno))

                    else:
                        raise Exception('Note data {} for unknown lane {} on line {}!'.format(note_data, msc_lane, lineno))

                    # if is_pending:

                    # if resolving_pending:
                    #     found = False
                    #     for i in range(len(pending_events)):
                    #         if (
                    #             pending_events[i][1]['kind'] == Constants.EVENT_KIND_HOLD and
                    #             pending_events[i][1]['lane'] == msc_lane
                    #         ):
                    #             pending_events[i][1]['end'] = int(curtime)
                    #             events.append(pending_events[i][1])
                    #             del pending_events[i]

                    #             found = True
                    #             break

                    #     if not found:
                    #         raise Exception('End hold note with no start hold found for lane {} on line {}!'.format(msc_lane, lineno))

                # Move ourselves forward past this time.
                curtime = curtime + ms_per_note

            # Finally, update our time
            return curtime

        for (lineno, line) in notedetails['data']:
            if line.strip().startswith(','):
                # Parse out current measure
                curtime = parse_measure(curtime, curmeasure)
                curmeasure = []
            else:
                curmeasure.append((lineno, line))

        for (lineno, evt) in pending_events:
            if evt['kind'] not in Constants.EVENT_CATEGORY_LARGE_SPINNERS:
                raise Exception('Note started on line {} for lane {} is missing end marker!'.format(lineno, evt['lane'] + 1))

        # Events can be generated out of order, so lets sort them!
        events = sorted(
            events,
            key=lambda event: event['start'],
        )

        return events

    @property
    def bpms(self) -> List[Tuple[float, float]]:
        bpms = []
        for line, bpm in self.metadata.get('bpms', {}):
            if '=' not in bpm:
                continue
            time_val, bpm_val = bpm.split('=', 1)
            timeval = float(time_val)
            bpmval = float(bpm_val)
            bpms.append((timeval, bpmval))

        return sorted(
            [(beat, bpm) for (beat, bpm) in bpms],
            key=lambda b: b[0]
        )

    @property
    def labels(self) -> List[Tuple[float, str]]:
        labels = []
        for line, label in self.metadata.get('labels', {}):
            if '=' not in label:
                continue
            time_val, label_text = label.split('=', 1)
            timeval = float(time_val)
            labels.append((timeval, label_text))

        return sorted(
            [(beat, label) for (beat, label) in labels],
            key=lambda b: b[0]
        )

class XMLv2:

    def __init__(self, chart: Chartv2, chartid: int) -> None:
        self.__chart = chart
        self.__id = chartid

    def get_notes(self, difficulty: str) -> bytes:
        # Grab the parsed event data for this difficulty.
        events = self.__chart.events.get(difficulty)

        if events is None:
            return b''

        # Parse out BPM, convert to milliseconds
        bpms = sorted(
            [(beat, bpm) for (beat, bpm) in self.__chart.bpms],
            key=lambda b: b[0]
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
        # TODO: support time signature changes
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
                Constants.EVENT_KIND_MEASURE_MARKER,
                Constants.EVENT_KIND_BEAT_MARKER,
                Constants.EVENT_KIND_GRAFICA_SECTION_START,
                Constants.EVENT_KIND_GRAFICA_SECTION_END,
            ]:
                # Special case, the lane doesn't matter for these as they're global.
                lane = kind

            if kind in [
                Constants.EVENT_KIND_HOLD,
                Constants.EVENT_KIND_LARGE_SPINNER,
                Constants.EVENT_KIND_LARGE_SPINNER_LEFT,
                Constants.EVENT_KIND_LARGE_SPINNER_RIGHT,
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

    def __add_metadata_to_document(
        self,
        music_data: minidom.Document,
    ) -> None:
        # Find MDB node
        mdb_nodes = music_data.getElementsByTagName('mdb')
        if len(mdb_nodes) != 1:
            raise Exception('Invalid XML file layout!')
        mdb = mdb_nodes[0]

        # Grab info
        infodict = self.__chart.metadata

        # Grab notes sections
        notedetails = self.__chart.notes

        # Parse out BPM
        bpms = self.__chart.bpms

        # Grab max and min BPM
        maxbpm = max([bpm for (_, bpm) in bpms])
        minbpm = min([bpm for (_, bpm) in bpms])

        def element(parent: Any, name: str, value: Optional[str]=None) -> Any:
            element = music_data.createElement(name)
            parent.appendChild(element)

            if value is not None:
                text = music_data.createTextNode(value)
                element.appendChild(text)

            return element

        # Create a single child with the right music ID
        music = element(mdb, 'music')
        music.setAttribute('id', str(self.__id))

        # Create info section for metadata
        info = element(music, 'info')

        # Copypasta into info the various data we should have
        element(info, 'label', str(self.__id))
        element(info, 'title_name', infodict.get('title', ''))
        element(info, 'title_yomigana', infodict.get('titletranslit', ''))
        element(info, 'artist_name', infodict.get('artist', ''))
        element(info, 'artist_yomigana', infodict.get('artisttranslit', ''))
        element(info, 'ascii', infodict.get('subtitletranslit', 'dummy'))
        element(info, 'bpm_min', str(int(minbpm * 100))).setAttribute('__type', 'u32')
        element(info, 'bpm_max', str(int(maxbpm * 100))).setAttribute('__type', 'u32')
        element(info, 'distribution_date', datetime.date.strftime(datetime.datetime.now(), "%Y%m%d")).setAttribute('__type', 'u32')  # type: ignore

        # TODO: Figure out what more of these should be (is_fixed???)
        element(info, 'volume', '90').setAttribute('__type', 'u16')
        element(info, 'bg_no', '0').setAttribute('__type', 'u16')
        element(info, 'genre', '16').setAttribute('__type', 'u8')
        element(info, 'is_fixed', '1').setAttribute('__type', 'u8')
        element(info, 'version', '1').setAttribute('__type', 'u8')
        element(info, 'demo_pri', '-2').setAttribute('__type', 's8')
        element(info, 'world', '0').setAttribute('__type', 'u8')
        element(info, 'tier', '0').setAttribute('__type', 's8')
        element(info, 'license', infodict.get('license', ''))
        element(info, 'vmlink_phase', '0').setAttribute('__type', 's32')
        element(info, 'inf_ver', '0').setAttribute('__type', 'u8')

        # Create difficulties section
        difficulty = element(music, 'difficulty')
        for (sm_diff, msc_diff) in [('easy', 'novice'), ('medium', 'advanced'), ('hard', 'exhaust'), ('expert', 'infinite')]:
            root = element(difficulty, msc_diff)
            if msc_diff != 'infinite':
                details = notedetails.get(sm_diff, {})
            else:
                details = {}  # type: Dict[str, str]

            element(root, 'difnum', details.get('rating', '0')).setAttribute('__type', 'u8')
            element(root, 'illustrator', infodict.get('credit', 'dummy'))
            element(root, 'effected_by', details.get('author', 'dummy'))
            element(root, 'price', '-2').setAttribute('__type', 's32')
            element(root, 'limited', '2' if (sm_diff == 'expert' or  details.get('rating', '0') == '0') else '3').setAttribute('__type', 'u8')

    def get_metadata(self) -> bytes:
        # Create root document
        music_data = minidom.Document()
        mdb = music_data.createElement('mdb')
        music_data.appendChild(mdb)

        # Add our info to the empty doc.
        self.__add_metadata_to_document(music_data)

        return music_data.toprettyxml(indent="  ", encoding='shift_jisx0213').replace(b'shift_jisx0213', b'shift-jis')

    def update_metadata(self, old_data: bytes) -> bytes:
        # Parse old root document, being sure to recognize the encoding lie
        try:
            datastr = old_data.decode('utf-8')
            encoding = 'utf-8'
        except UnicodeDecodeError:
            try:
                datastr = old_data.decode('shift_jisx0213')
                encoding = 'shift_jisx0213'
            except UnicodeDecodeError:
                raise Exception('Unable to parse exising XML data!')

        music_data = minidom.parseString(datastr)
        mdb = music_data.createElement('mdb')

        # First, find and delete any music entries matching our ID
        for node in music_data.getElementsByTagName('music'):
            idattr = node.attributes.get('id')
            if idattr is not None:
                idval = str(idattr.value)
                if idval == str(self.__id):
                    parent = node.parentNode
                    parent.removeChild(node)

        # Now, add our info to the updated doc
        self.__add_metadata_to_document(music_data)

        newdata = music_data.toprettyxml(indent="  ", encoding=encoding).replace(encoding.encode('ascii'), b'shift-jis')

        # For some reason, minidom loves adding tons of whitespace, so lets
        # hack it back out.
        return b'\n'.join([
            line for line in newdata.split(b'\n')
            if len(line.strip()) > 0
        ])
