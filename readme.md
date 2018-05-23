# MÚSECA Chart Converter

This utility includes a chart converter that can convert a set of charts written in StepMania's .ssc file format and an audio file to a format recognized by MÚSECA. Additionally, it will generate metadata to copy-paste into the music database xml, or optionally update an xml file if provided. It is invoked similar to the following:

    python3 ssc2museca.py chart.ssc 123

In the above command, a chart for Novice (Green), Advanced (Yellow), and Exhaust (Red) will be parsed out of ``chart.ssc`` and metadata and a directory suitable for copying into MÚSECA's game data will be generated. The game will identify the entry as ID 123. Note that you will probably want to choose IDs that are not already taken in the music database xml unless you want to replace songs in the game instead of add songs to the game. By default, the converter will output the converted metadata, chart and audio files to the current directory. To specify a separate directory, use ``--directory some/dir``. To tell the converter to update an existing xml file instead of generating a copy-pastable chunk of xml, use ``--update-xml music-info.xml``.

## About This Fork

This fork is designed to be used in conjunction with [https://github.com/theKeithD/sm2museca](a fork of StepMania 5.2 that adds a new ``museca-single`` game mode). This mode defines a 16-lane single player mode, rather than a 16-lane double play mode like the ones offered by ``bm`` and ``techno``.

_(Binaries to be provided soon)_

## Dependencies

The following dependencies are required to run this conversion software:

- ffmpeg - Used to convert various audio formats to the ADPCM format required by MÚSECA.
- sox - Used to create preview clips.
- python3 - The script assumes python 3.5 or better to operate.
- MÚSECA cabinet - Obviously you'll need to have access to one of these to test and play songs.

## Caveats

While it is possible to also update the album art (both the jacket and the background on the result screen and the music select screen), the converter does not currently automate the process. I recommend looking into mon's IFS tools to do this. The background on the results screen is just a .png file named correctly (based on the ID), and the jacket is in a .ifs file named either ``pix_jk_s.ifs`` or ``pix_jk_s_2.ifs`` depending on the song's ID. You will want to add jackets for new songs to ``pix_jk_s_2.ifs``.

Note that the game supports time signatures other than 4/4 but the converter doesn't make any attempt to handle this. It also DOES technically support BPM changes, but no verification was done around this feature. The converter will probably let you put down illegal sequences, such as a small/large spinny boi on top of a regular note. The game engine may actually handle this, but there is no guarantee!

# Chart Format

## Header Tags

* ``TITLE`` - The title of the song as it shows in-game. This can be any unicode characters, including english, kana or kanji.
* ``TITLETRANSLIT`` - The title of the song as sounded out in katakana, with dakuten and in half-width. This is used for title sort. There are converters which take any english and give you the katakana, and converters that go from full-width to half-width katakana. Use them!
* ``ARTIST`` - The artist of the song as it shows in-game. This can be any unicode characters, including english, kana or kanji.
* ``ARTISTTRANSLIT`` - The artist of the song as sounded out in katakana, with dakuten and in half-width. This is used for artist sort. There are converters which take any english and give you the katakana, and converters that go from full-width to half-width katakana. Use them!
* ``SUBTITLETRANSLIT`` - This maps to the ``ascii`` element in music-info.xml, and defaults to "``dummy``". Can (and should) be left blank.
* ``MUSIC`` - Path to an audio file to be converted. Use any format supported by ffmpeg.
* ``SAMPLESTART`` - Number of seconds into the above music to start the preview. The converter will auto-fade in and convert to a preview song.
* ``SAMPLELENGTH`` - Number of seconds after the start to continue playing the preview before cutting off. The game tends to use 10-second previews, so its wise to stick with that.
* ``OFFSET`` - Number of seconds to offset the chart relative to the start of the music. Use this to sync the game to the chart.
* ``BPMS`` - What BPM the chart is at. For help on this field, please refer to [https://github.com/stepmania/stepmania/wiki/ssc](the .ssc format documentation). It is not a simple number, but instead a comma-separated list of timestamps in seconds paired to a BPM that the song uses at that point.
* ``LICENSE`` - The license owner of the song. Can be left blank.
* ``CREDIT`` - The illustration artist. Can be left blank.

### More chart format
Each chart begins with a `#NOTEDATA:;` line. The following tags after `#NOTEDATA:;` are used by the converter:
- ``#STEPSTYPE`` - The only supported type is ``museca-single``.
- ``#CREDIT`` - The author of the chart, AKA your handle. Not to be confused with the ``#CREDIT``
- ``#DIFFICULTY`` - One of the following three supported difficulties: ``Easy``, ``Medium``, or ``Hard``.
- ``#METER`` - The difficulty rating, as a value from 1-15 inclusive.
- ``#NOTES`` - The actual note data, which will continue to be parsed until a line with only a  ``;`` on it is encountered.


## Lane Layout, Charting, and Design Notes

There is 1 pedal lane, and then 3 channels of 5 lanes each.

    CH0 @ sm[0]:      pedal (note that in museca, this lane is actually on the far right at ``msc[5]``)
    CH1 @ sm[1..5]:   taps and holds
    CH2 @ sm[6..10]:  left spins
    CH3 @ sm[11..15]: right spins

### Mapping Examples
- **Tap** in CH1, ``sm[1]``
    - **Tap** in ``msc[1]``
- **Hold** in CH1, ``sm[1]``
    - **Hold** in ``msc[1]``
- **Tap** in CH2, ``sm[6]``
    - **Left spin** in ``msc[1]``
- **Tap** in CH3, ``sm[11]``
    - **Right spin** in ``msc[1]``
- **Tap** in CH2 and CH3, ``sm[6] and sm[11]`` 
    - **Non-directional spin** in ``msc[1]``
- **Hold *start*** in CH2 or CH3, ``sm[6] or sm[11]``
    - **Start storm object event** in ``msc[1]``
- **Mine** in CH1 or CH2 or CH3, ``sm[1] or sm[6] or sm[11]``
    - **End storm object event** in ``msc[1]``

### Why 3 Channels?
- Hold ends in StepMania don't have multiple end types, so we can't overlap a spinner of any kind onto a hold release.
- More taps means more claps, which is always nice.
    - An original 6-lane draft made use of all 4 note types: Tap, Mine (left spin), Fake (right spin), Lift (non-dir spin)
    - But there were still hold ends and storm objects to worry about, thus...

### Storm Objects: Why Hold Start, Why Mines?
- Storm objects are "like" holds in that they have a start and end...
    - ...but they do not claim exclusive control of the lane in MÚSECA.
    - While a storm object is out, that lane could have taps and spins going on!
- To still retain the assist tick sound while distinguishing these from normal spins, we make a hold, rather than a lift/fake.
    - The timing of the hold end does not matter, the converter should ignore hold end events in CH2 or CH3.
- The mine will indicate the storm is over, but it can go in any 5-lane channel, even CH1.
    - This way, a storm object can end at the same time a spin of any kind occurs in that lane. (mine goes in CH1, taps go in CH2+CH3)
- There's still one imperfect situation...

### Case(s) Not Covered
- Storm end event in ``msc[1]`` at the same time as a non-directional spin acting as the "tail" of a hold in ``msc[1]``. (or acting as the "head", but that's evil)
    - Where does the mine go? CH1 is occupied by a hold, CH2 and CH3 are occupied by taps that will become a non-directional spin.
    - Either shift something (preferably the mine/stormend) by 1/192nd...
    - ...or maybe add a Label called "``STORM_END_LANE_n``" at this point, which will tell the converter to create a storm end event in lane ``n``.

### TODO
- Grafica gates are planned to be events within #LABELS.
  1. This will require the converter to parse the #LABELS list.
  2. And then perform some basic sanity checks. (START -> END -> START -> END -> START -> END)
    - The label names will follow a pattern of ``GRAFICA_n_[START|END]``, where ``[n]`` is a value from 1-3 inclusive.
  3. And then convert the beat numbers used into milliseconds.
  4. And then push these to the events list.

## Example chart

Below is an example chart, which includes a few measures showcasing a handful of events:

    #VERSION:0.83;
    #TITLE:双翼の独奏歌;
    #ARTIST:ダークイルミネイト;
    #TITLETRANSLIT:ｿｳﾖｸﾉｱﾘｱ;
    #ARTISTTRANSLIT:ﾀﾞｰｸｲﾙﾐﾈｲﾄ;
    #CREDIT:Bandai Namco Entertainment Inc.;
    #BANNER:banner.jpg;
    #BACKGROUND:end.jpg;
    #DISCIMAGE:;
    #MUSIC:aria.wav;
    #OFFSET:0.000000;
    #SAMPLESTART:72.680000;
    #SAMPLELENGTH:13.083000;
    #SELECTABLE:YES;
    #BPMS:0.000=170.000;
    #TIMESIGNATURES:0.000=4=4;
    #TICKCOUNTS:0.000=4;
    #COMBOS:0.000=1;
    #SPEEDS:0.000=1.000=0.000=0;
    #SCROLLS:0.000=1.000;
    #LABELS:0.000=Song Start,
    72.000=GRAFICA_1_START,
    104.000=GRAFICA_1_END,
    208.000=GRAFICA_2_START,
    271.000=GRAFICA_2_END,
    272.000=GRAFICA_3_START,
    316.000=GRAFICA_3_END;
    #BGCHANGES:0.000=-songbackground-=1.000=0=0=0=StretchNoLoop====,
    99999=-nosongbg-=1.000=0=0=0 // don't automatically add -songbackground-
    ;


    //---------------museca-single - ----------------
    #NOTEDATA:;
    #STEPSTYPE:museca-single;
    #DIFFICULTY:Hard;
    #METER:15;
    #RADARVALUES:0.424903,1.104567,0.186425,0.194899,0.419456,351.000000,319.000000,22.000000,23.000000,6.000000,12.000000,0.000000,0.000000,0.000000,0.424903,1.104567,0.186425,0.194899,0.419456,351.000000,319.000000,22.000000,23.000000,6.000000,12.000000,0.000000,0.000000,0.000000;
    #CREDIT:K;
    #NOTES:
    // measure 0
    0000000000000000
    0000000000000000
    0000000000000000
    0000000000000000
    ,  // measure 1
    2000000000000000
    0000000000000000
    0000000000000000
    0000000000000000
    0000000000000000
    0000000000000000
    0000000000000000
    0000000000000000
    0000000010000200
    0000000000000300
    0000000000000000
    0000000000000000
    0000000100000010
    0000000000000000
    0000000000000000
    0000000000000000
    ,  // measure 2
    3100000000000M00
    0001000000000000
    0000010000000000
    0000100000000000
    0010000000000000
    0000100000000000
    0000010000000000
    0001000000000000
    0100000000000000
    0010000000000000
    0000100000000000
    0010000000000000
    0100000000000000
    0001000000000000
    0000010000000000
    0000100000000000
    ,  // measure 3
    0010000000000000
    0100000000000000
    0001000000000000
    0000010000000000
    0000100000000000
    0010000000000000
    0000100000000000
    0000010000000000
    0001000000000000
    0100000000000000
    0010000000000000
    0000100000000000
    0010000000000000
    0100000000000000
    0001000000000000
    0000010000000000
    ,  // measure 4
    0001000000000000
    0010000000000000
    0000100000000000
    0100000000000000
    0000010000000000
    0100000000000000
    0000100000000000
    0010000000000000
    0001000000000000
    0000010000000000
    0100000000000000
    0010000000000000
    0000100000000000
    0000010000000000
    0001000000000000
    0010000000000000
    ,  // measure 5
    0100000000000000
    0010000000000000
    0001000000000000
    0000100000000000
    0000010000000000
    0010000000000000
    0000100000000000
    0100000000000000
    0001000000000000
    0000100000000000
    0000010000000000
    0000100000000000
    0001000000000000
    0010000000000000
    0000010000000000
    0001000000000000

    [--snip--]

    ,  // measure 77
    2200022000110002
    3000003000000003
    0000000000000000
    0000000000000000
    0000000000000000
    0000000000000000
    0000000000000000
    0000000000000000
    0000000000000000
    0000000000000000
    0000000000000000
    0000000000000000
    0000000000000000
    0000000000000000
    0000000000000000
    0000000000000000
    ,  // measure 78
    0000000000000000
    2000000000000000
    0000000000000000
    0000000000000000
    0000000000000000
    0000000000000000
    0000000000000000
    0000000000000000
    ,  // measure 79
    3300031000MM0001
    0000000000000000
    0000000000000000
    0000000000000000
    ;