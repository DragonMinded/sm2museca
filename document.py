import datetime

from typing import Dict, Any, Optional
from xml.dom import minidom  # type: ignore

from chart import Chart
from misc import Constants


class XML:

    def __init__(self, chart: Chart, chartid: int) -> None:
        self.__chart = chart
        self.__id = chartid

    def get_notes(self, difficulty: str) -> bytes:
        # Grab the parsed event data for this difficulty.
        events = self.__chart.events.get(difficulty)

        if events is None:
            return b''

        # Parse out BPM, convert to milliseconds
        bpms = sorted(
            [(ts * 1000.0, bpm) for (ts, bpm) in self.__chart.bpms],
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
                details = {}  # type: Dict[str, str]

            element(root, 'difnum', details.get('rating', '0')).setAttribute('__type', 'u8')
            element(root, 'illustrator', infodict.get('credit'))
            element(root, 'effected_by', details.get('author'))
            element(root, 'price', '-1').setAttribute('__type', 's32')
            element(root, 'limited', '1' if (diffval == 'infinite' or details.get('rating', '0') == '0') else '3').setAttribute('__type', 'u8')

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
        music_data.createElement('mdb')

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
