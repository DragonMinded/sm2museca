import argparse
import datetime
import os
import sys

from typing import Dict, Any, List, Tuple, Optional
from xml.dom import minidom  # type: ignore

from chart import Chart, XML
from audio import TwoDX, ADPCM

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
    parser.add_argument(
        "-x",
        "--update-xml",
        help="Location of music database XML file to update. If not specified, "
             "a new one will be created containing just the data for this file.",
        default=None,
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

    print('Parsing chart data...')

    # First, parse out the chart and get the XML writer ready.
    chart = Chart(data)
    xml = XML(chart, args.id)

    print('Outputting XML...')

    if args.update_xml is not None:
        # First, update the metadata file with the info from this chart.
        fp = open(args.update_xml, "rb")
        data = fp.read()
        fp.close()
        fp = open(args.update_xml, "wb")
        fp.write(xml.update_metadata(data))
        fp.close()
    else:
        # First, write out a metadata file, that can be copied into music-info.xml
        fp = open(os.path.join(root, 'music-info.xml'), 'wb')
        fp.write(xml.get_metadata())
        fp.close()

    # Now, write out the chart data
    fp = open(os.path.join(root, '01_{num:04d}_nov.xml'.format(num=args.id)), 'wb')
    fp.write(xml.get_notes('novice'))
    fp.close()

    # Now, write out the chart data
    fp = open(os.path.join(root, '01_{num:04d}_adv.xml'.format(num=args.id)), 'wb')
    fp.write(xml.get_notes('advanced'))
    fp.close()

    # Now, write out the chart data
    fp = open(os.path.join(root, '01_{num:04d}_exh.xml'.format(num=args.id)), 'wb')
    fp.write(xml.get_notes('exhaust'))
    fp.close()

    # Write out miscelaneous files
    fp = open(os.path.join(root, '01_{num:04d}.def'.format(num=args.id)), 'wb')
    fp.write('#define 01_{num:04d}   0\n'.format(num=args.id).encode('ascii'))
    fp.close()
    fp = open(os.path.join(root, '01_{num:04d}_prv.def'.format(num=args.id)), 'wb')
    fp.write('#define 01_{num:04d}_prv   0\n'.format(num=args.id).encode('ascii'))
    fp.close()

    # Now, if we have an audio file, convert that too
    musicfile = chart.metadata.get('music')
    if musicfile is not None:
        # Make sure we also provided a sample start/offset
        preview_start = chart.metadata.get('samplestart')
        preview_length = chart.metadata.get('samplelength')

        if preview_start is None:
            raise Exception('Music file present but no sample start specified for preview!')
        sample_start = float(preview_start)
        if preview_length is None:
            print('WARNING: No sample length specified, assuming 10 seconds!', file=sys.stderr)
            sample_length = 10.0
        else:
            sample_length = float(preview_length)

        print('Converting audio...')

        adpcm = ADPCM(musicfile, sample_start, sample_length)

        twodx = TwoDX()
        twodx.set_name('01_{num:04d}'.format(num=args.id))
        twodx.write_file('01_{num:04d}_1.wav'.format(num=args.id), adpcm.get_full_data())

        fp = open(os.path.join(root, '01_{num:04d}.2dx'.format(num=args.id)), 'wb')
        fp.write(twodx.get_new_data())
        fp.close()

        print('Converting preview...')

        twodx = TwoDX()
        twodx.set_name('01_{num:04d}_prv'.format(num=args.id))
        twodx.write_file('01_{num:04d}_prv_1.wav'.format(num=args.id), adpcm.get_preview_data())

        fp = open(os.path.join(root, '01_{num:04d}_prv.2dx'.format(num=args.id)), 'wb')
        fp.write(twodx.get_new_data())
        fp.close()

    print('Done!')

    return 0

if __name__ == '__main__':
    sys.exit(main())
