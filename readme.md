# MÚSECA Chart Converter

This utility defines a chart format similar to the StepMania chart format, and includes a chart converter that can convert a set of charts and an audio file to a format recognized by MÚSECA. Additionally, it will generate metadata to copy-paste into the music database xml, or optionally update an xml file if provided. It is invoked similar to the following:

    python3 sm2museca.py chart.mu 123

In the above command, a chart for Novice, Advanced and Exhaust will be parsed out of ``chart.mu`` and metadata and a directory suitable for copying into MÚSECA's game data will be generated. The game will identify the entry as ID 123. Note that you will probably want to choose IDs that are not already taken in the music database xml unless you want to replace songs in the game instead of add songs to the game. By default, the converter will output the converted metadata, chart and audio files to the current directory. To specify a separate directory, use ``--directory some/dir``. To tell the converter to update an existing xml file instead of generating a copy-pastable chunk of xml, use ``--update-xml music-info.xml``.

## Dependencies

The following dependencies are required to run this conversion software:

* ffmpeg - Used to convert various audio formats to the ADPCM format required by MÚSECA.
* sox - Used to create preview clips.
* python3 - The script assumes python 3.5 or better to operate.
* MÚSECA cabinet - Obviously you'll need to have access to one of these to test and play songs.

## Caveats

While it is possible to also update the album art (both the jacket and the background on the result screen and the music select screen), the converter does not currently automate the process. I recommend looking into mon's IFS tools to do this. The background on the results screen is just a .png file named correctly (based on the ID), and the jacket is in a .ifs file named either ``pix_jk_s.ifs`` or ``pix_jk_s_2.ifs`` depending on the song's ID. You will want to add jackets for new songs to ``pix_jk_s_2.ifs``.

Note that the game supports time signatures other than 4/4 but the converter doesn't make any attempt to handle this. It also DOES technically support BPM changes, but no verification was done around this feature. The converter will probably let you put down illegal sequences, such as a small/large spinny boi on top of a regular note. The game engine may actually handle this, but there is no guarantee!

# Chart Format

StepMania's github account has an excellent writeup on the .sm file format that I've taken heavy inspiration (read: stolen) from. You can find [basic information here](https://github.com/stepmania/stepmania/wiki/sm). I'll assume familiarity with this format for the rest of the documentation.

## Required Header Tags

* TITLE - The title of the song as it shows in-game. This can be any unicode characters, including english, kana or kanji.
* TITLE_YOMIGANA - The title of the song as sounded out in katakana, with dakuten and in half-width. This is used for title sort. There are converters which take any english and give you the katakana, and converters that go from full-width to half-width katakana. Use them!
* ARTIST - The artist of the song as it shows in-game. This can be any unicode characters, including english, kana or kanji.
* ARTIST_YOMIGANA - The artist of the song as sounded out in katakana, with dakuten and in half-width. This is used for artist sort. There are converters which take any english and give you the katakana, and converters that go from full-width to half-width katakana. Use them!
* MUSIC - Path to an audio file to be converted. Use any format supported by ffmpeg.
* SAMPLESTART - Number of seconds into the above music to start the preview. The converter will auto-fade in and convert to a preview song.
* SAMPLELENGTH - Number of seconds after the start to continue playing the preview before cutting off. The game tends to use 10-second previews, so its wise to stick with that.
* OFFSET - Number of seconds to offset the chart relative to the start of the music. Use this to sync the game to the chart.
* BPMS - What BPM the chart is at. For help on this field, please refer to the SM writeup above. Its not a simple number, but instead a comma-separated list of timestamps in seconds paired to a BPM that the song uses at that point.
* LICENSE - The license owner of the song. Can be left blank.
* CREDIT - The illustration artist. Can be left blank.

## Notes

Exactly like the .sm format, the NOTES section includes information about the chart itself followed by measure data. Unlike the .sm format, there is no groove radar values entry because MÚSECA doesn't have a groove radar. The following is a description of the metadata that is required:

* Chart type - The only supported type is ``museca-single``.
* Description/author - The author of the chart, AKA your handle.
* Difficulty - One of the following three supported difficulties: ``Novice``, ``Advanced``, or ``Exhaust``.
* Numerical meter - The difficulty rating, as a value from 1-15 inclusive.

Measure data is identical to the .sm format, where we support 4ths, 8ths, 12ths, 16ths, etc. As a convenience, we also support whole note measures, usually used for having a whole measure of nothing. The position of the character indicates the lane, much like in .sm. Postion 1-5 are lanes 1-5 in game, and position 6 is the foot pedal. Clever readers will note that the .sm format doesn't support multiple events at the same time. This presents a problem if you want to have a hold note, and then add a spinny boi on the hold lift, as a lot of official charts do. As an extension of the format, you can add a second identical set of notes to the right of the first, separated by a space. The note values are slightly different than .sm as well, given that there's a lot more possible note types. They're documented below.

* 0 - No note.
* 1 - Normal note (a tap).
* 2 - Hold start (start of a hold note). Note that this is the only valid entry that can go in the foot pedal lane.
* 3 - Hold end (end of a hold note). Note that this is the only valid entry that can go in the foot pedal lane.
* s - Spinny boi.
* l - Left direction spinny boi.
* r - Right direction spinny boi.
* S - Large spinny boi start. In game, the tornado effect is controlled by placing a large spin end event when you want it to land.
* L - Left direction large spinny boi.
* R - Right direction large spinny boi.
* T - Large spin finish. This is the point in which a previously started large spinny boi's tornado will land.
* G - Grafica gate. The game normally has three sections where a grafica's effects are used. Grafica gates are used to toggle being in a grafica effect section. Unlike the rest of the events, this can be placed on any lane.

## Example chart

Below is an example chart, in which I show off the use of each different note type, as well as a few concurrent events.

    #TITLE:Call Me Maybe;
    #TITLE_YOMIGANA:ｺｰﾙﾐｰﾒｰﾋﾞｰ;
    #ARTIST:Carly Rae Jephsen;
    #ARTIST_YOMIGANA:ｶｰﾘｰﾚｰｼﾞｪﾌｾﾝ;
    #MUSIC:Carly Rae Jepsen - Call Me Maybe.mp3;
    #SAMPLESTART: 28.500;
    #SAMPLELENGTH: 10.000;
    #OFFSET:0.000;
    #BPMS:0.000=120.000;
    #LICENSE:;
    #CREDIT:DragonMinded;
    #NOTES:
        museca-single:
        DragonMinded:
        Novice:
        5:
    000000
    ,
    000000
    ,
    000000
    ,
    000000
    ,
    100000
    010000
    001000
    000100
    ,
    000010 000002
    000100
    001000
    010000
    ,
    100000 000003
    000000
    000000
    000000
    ,
    101000
    010100
    001010
    0l0l00
    001010
    010100
    101000
    0r0r00
    ,
    000000
    ,
    200000
    000000
    300020 s00000
    000000
    ,
    000030 0000s0
    000000
    000000
    000000
    ,
    00S000
    ,
    L0T0R0
    000000
    000000
    000000
    ,
    T000T0
    ,
    000000
    ,
    000000
    ,
    000000
    ,
    000000
    ,
    000000
    ,
    000000
    ,
    000000
    ,
    000000
    ;
    #NOTES:
        museca-single:
        DragonMinded:
        Advanced:
        10:
    ;
    #NOTES:
        museca-single:
        DragonMinded:
        Exhaust:
        15:
    ;
