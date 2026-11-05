import argparse
from pathlib import Path
import sys
import time

from . import __version__

DESCRIPTION = ("Prepare songs for band practice: download, key and tempo detection, click tracks, "
               "transposition, speed changes and stem separation.")

EPILOG = """\
examples:
  song-wizard download "https://.../playlist?list=..."
  song-wizard key ~/Music/Show
  song-wizard bpm ~/Music/Show
  song-wizard click 120 --duration 4:30
  song-wizard align "song.opus"
  song-wizard transpose -2 "song.opus"
  song-wizard speed 80 "song.opus"
  song-wizard separate --stem drums ~/Music/Show
  song-wizard separate --stem vocals --stem guitar "song.opus"
  song-wizard separate --stem all "song.opus"
  song-wizard convert "song (no drums).opus"
  song-wizard rename "001 - Song (Official Video).opus" "Song"
  song-wizard trim "001 - Song.opus" --start 0:12.5 --end 3:58
  song-wizard delete "001 - Song.opus"
  song-wizard list cryin --files
  song-wizard reaper "001 - Song.opus"
  song-wizard archives --update all
  song-wizard ui
  song-wizard report

run "song-wizard COMMAND --help" for the options of each command.
"""


def build_parser():
    parser = argparse.ArgumentParser(prog="song-wizard", description=DESCRIPTION, epilog=EPILOG,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", metavar="COMMAND")

    p = sub.add_parser("download", help="download the audio of a link (a song or a playlist), without re-encoding",
                       description="Download the audio of a link, a single song or a playlist, in the best quality "
                                   "available and without re-encoding. Playlists go to <Music>/<playlist "
                                   "name>/001 - Artist - Title.opus (as the song's data says), single songs "
                                   "to <Music>/Singles/. <Music> is $SONG_WIZARD_DIR if set, else your Music "
                                   "folder (the Windows one on WSL). An archive per playlist is kept: running "
                                   "it again only downloads new songs.")
    p.add_argument("--wav", action="store_true", help="also write a .wav next to each .opus")
    p.add_argument("--to", metavar="FOLDER",
                   help="where a new playlist's folder goes (default: the music folder); a playlist downloaded "
                        "before goes on in its own folder, wherever it is")
    p.add_argument("url", help="link to a song or a playlist")
    p.add_argument("ytdlp_args", nargs=argparse.REMAINDER, metavar="...",
                   help="extra yt-dlp options, e.g. --cookies-from-browser chrome")

    p = sub.add_parser("key", help="detect the key of songs",
                       description="Detect the key of each song. 4/4 means all four detection methods agree; "
                                   "lower counts are worth checking by ear. The most common mix-up is with "
                                   "the relative key, which is always shown.")
    p.add_argument("paths", nargs="+", metavar="FILE|FOLDER")
    p.add_argument("--set", metavar="KEY", help="don't detect: save this key for the songs (Am, C#, 'Bb major'); "
                                                  "detecting again keeps it unless --force")
    p.add_argument("--force", action="store_true", help="detect again also where the key was set by hand")

    p = sub.add_parser("bpm", help="detect the tempo of songs",
                       description="Detect the tempo of each song and how steady it is. Songs recorded without "
                                   "a click drift, so a range is shown instead. Like any tempo detector it can "
                                   "land on half or double the real tempo; uncertain results say so.")
    p.add_argument("paths", nargs="+", metavar="FILE|FOLDER")
    p.add_argument("--set", metavar="BPM", help="don't detect: save this tempo for the songs (120 or 98.5); "
                                                  "detecting again keeps it unless --force")
    p.add_argument("--force", action="store_true", help="detect again also where the tempo was set by hand")

    p = sub.add_parser("click", help="make a steady click track at a given tempo, meter and length",
                       description='Writes "Click 120 BPM 4-4.wav" in the current folder (or where -o says), '
                                   "with the first beat of each bar accented. The length is rounded up to whole "
                                   "bars. Clicks are placed from the tempo alone, so there is no drift however "
                                   "long it is.")
    p.add_argument("bpm", type=float, help="tempo, decimals allowed (e.g. the number from song-wizard bpm)")
    p.add_argument("--meter", default="4/4",
                   help="time signature; the top number is the clicks per bar (default: 4/4)")
    length = p.add_mutually_exclusive_group()
    length.add_argument("--duration", metavar="M:SS", help="length, e.g. 4:30 or 270 seconds (default: 1:00)")
    length.add_argument("--bars", type=int, help="length in bars")
    length.add_argument("--like", metavar="FILE", help="as long as this song (and named after it, like --for)")
    p.add_argument("--subdivide", type=int, default=1, metavar="N",
                   help="softer clicks between beats: 2 = eighths, 3 = triplets, 4 = sixteenths")
    p.add_argument("--for", dest="song", metavar="FILE",
                   help='name it after this song, "Title (click 120 BPM 4-4).wav", and save it next to it')
    p.add_argument("-o", "--output", metavar="PATH", help="output file or folder")

    p = sub.add_parser("align", help="find a song's exact tempo and first beat, for a click that plays along",
                       description="Detects the exact tempo (with decimals) and when the first beat falls, and "
                                   "saves them in click.txt next to the song, where the practice player of "
                                   '"song-wizard ui" reads them to play a click along with the song. --bpm and '
                                   "--first set them by hand instead (a detected tempo can be half or double the "
                                   "real one).")
    p.add_argument("--bpm", type=float, help="tempo, instead of detecting it")
    p.add_argument("--first", type=float, metavar="SECONDS", help="time of the first beat, instead of detecting it")
    p.add_argument("--meter", default="4/4", help="time signature (default: 4/4)")
    p.add_argument("paths", nargs="+", metavar="FILE|FOLDER")

    p = sub.add_parser("chords", help="detect the chords of songs, to read them in the practice player",
                       description="Detects each song's chords and saves them next to it as "
                                   "\"<song>.chords.json\", which the practice player of \"song-wizard ui\" shows "
                                   "and lets you correct. The chords are moved onto the song's beats, so it needs its "
                                   "click (click.txt); a song without one gets it first, as with song-wizard align. "
                                   "Chords corrected by hand are kept unless --force. The first time, it downloads "
                                   "its model (12 MB).")
    p.add_argument("paths", nargs="+", metavar="FILE|FOLDER")
    p.add_argument("--force", action="store_true", help="detect again also the chords corrected by hand")

    p = sub.add_parser("notes", help="detect the notes the bass and the voice play, from their stems",
                       description="Follows the notes of the separated bass (pYIN) and voice (CREPE) and saves "
                                   "them next to the song as \"<song>.notes.json\", which the practice player of "
                                   "\"song-wizard ui\" shows, plays and lets you correct. It needs the stems: "
                                   "song-wizard separate --stem bass / --stem vocals. One line at a time: where "
                                   "several voices sing at once, it follows one. Notes corrected by hand are kept "
                                   "unless --force. The first time, it downloads the voice model (89 MB).")
    p.add_argument("paths", nargs="+", metavar="FILE|FOLDER")
    p.add_argument("--part", choices=["bass", "vocals"], help="only this one (both by default)")
    p.add_argument("--force", action="store_true", help="detect again also the notes corrected by hand")

    p = sub.add_parser("drums", help="detect what the drums play, to print it as a drum sheet",
                       description="Finds the drums' hits (kick, snare, toms, hi-hat open and closed, ride, crash) "
                                   "and saves them next to the song as \"<song>.drums.json\", which the practice "
                                   "player of \"song-wizard ui\" plays and prints as a drum sheet. It uses ADTOF, a "
                                   "model with its own license (CC BY-NC-SA 4.0: non-commercial use only), "
                                   "downloaded once (2.2 MB) after asking. It needs the song's click (click.txt; found "
                                   "first if missing) and its drum kit stems (separated first if missing). With "
                                   "--sheet or --midi it writes what was detected as \"<song>.drums.html\" (to print) "
                                   "or \"<song>.drums.mid\" (for REAPER or another program).")
    p.add_argument("paths", nargs="+", metavar="FILE|FOLDER")
    p.add_argument("--force", action="store_true", help="detect again also the hits put in by hand")
    p.add_argument("--accept-model-license", action="store_true",
                   help="download the model without asking (its license: CC BY-NC-SA 4.0, non-commercial use only)")
    p.add_argument("--sheet", action="store_true", help='write the drum sheet, "<song>.drums.html"')
    p.add_argument("--midi", action="store_true", help='write the hits as MIDI, "<song>.drums.mid"')
    p.add_argument("--full", action="store_true", help="with --sheet: every bar written, none folded")

    p = sub.add_parser("transpose", help="shift songs up or down by semitones",
                       description='Shift pitch without changing tempo or timing. Writes "Title (+2).opus" '
                                   '(or .wav/.mp3, as [audio] stems in the settings says) next to the original.')
    p.add_argument("semitones", type=float, metavar="N",
                   help="semitones: +1 = half step up, +2 = whole step up, -1.5, ...")
    p.add_argument("paths", nargs="+", metavar="FILE|FOLDER")

    p = sub.add_parser("speed", help="slow songs down or speed them up without changing the pitch",
                       description='Change the speed without changing the pitch. Writes "Title (80%%).opus" '
                                   "(or .wav/.mp3, as [audio] stems in the settings says) next to the original; "
                                   'with --semitones, also shifts the pitch in the same pass: "Title (80%%, -2).opus".')
    p.add_argument("percent", type=float, metavar="PERCENT",
                   help="speed in percent of the original: 80 = slower, 120 = faster (25 to 200)")
    p.add_argument("--semitones", type=float, default=0, metavar="N", help="also shift the pitch, like transpose")
    p.add_argument("paths", nargs="+", metavar="FILE|FOLDER")

    from .separate import ALL, STEMS
    p = sub.add_parser("separate", help="split out instruments: the instrument alone plus everything else",
                       description='For each --stem, writes "Title (drums).opus" (the instrument alone) and '
                                   '"Title (no drums).opus" (everything else) next to the original; with '
                                   'stems = "wav" under [audio] in the settings, 32-bit float WAV. The two add up '
                                   "to the original (to the sample in WAV). Models are "
                                   "downloaded the first time they are used. Runs on an NVIDIA GPU (GTX 16 / "
                                   "RTX 20 or newer) or an Apple Silicon GPU when available, else on the CPU.")
    p.add_argument("--stem", action="append", required=True, choices=[*STEMS, ALL],
                   help='instrument to separate; repeat for several. "all" writes the four '
                        'instruments plus "Title (other).opus" (everything else: keys, synths, '
                        'backing vocals...), without the "no X" files; the five add up to the original. '
                        '"piano" isn\'t part of "all". "drumkit" splits the drums (separated first if '
                        'missing) into kick, snare, toms, hihat, ride and crash, plus "drums rest"; '
                        'together they add up to the drums')
    p.add_argument("--cpu", action="store_true",
                   help="use the CPU even if a GPU is available (slower, but avoids GPU problems)")
    p.add_argument("paths", nargs="+", metavar="FILE|FOLDER")

    from .convert import FORMATS
    p = sub.add_parser("convert", help="convert to MP3 (or M4A) to share, e.g. over WhatsApp",
                       description="Converts to a small format any phone plays: MP3 at ~190 kbps by default "
                                   '(about 7 MB for 5 minutes), or M4A (AAC). Writes "Title.mp3" next to each '
                                   "file. Given a folder, lossless files (WAV, FLAC, AIFF) and the stems and versions made in Opus are "
                                   "converted, not the downloaded songs; "
                                   "files named explicitly are converted whatever their format. Files whose "
                                   "peaks go above 0 dB are turned down just enough not to clip.")
    p.add_argument("--format", choices=list(FORMATS), default="mp3", help="output format (default: mp3)")
    p.add_argument("--overwrite", action="store_true", help="replace files that already exist")
    p.add_argument("paths", nargs="+", metavar="FILE|FOLDER")

    p = sub.add_parser("rename", help="rename a song together with its stems, versions and results",
                       description="Renames the song and every file made from it (other formats, stems, "
                                   'transposed and sped-up versions), and its lines in key.txt and bpm.txt. '
                                   'The "001 - " numbering is kept unless the new name has its own. If any new '
                                   "name is taken, nothing is renamed.")
    p.add_argument("path", metavar="FILE", help="the song, or any file made from it")
    p.add_argument("name", metavar="NEW_NAME", help="the new name, without extension")

    p = sub.add_parser("tag", help="see or change a song's data (title, artist, album, year, genre...)",
                       description="Without options, shows the data the file keeps (what music players show). "
                                   "--set and --unset change it in the song and every file made from it (other "
                                   "formats, stems, versions), all of them or none; REAPER takes are left alone. A "
                                   'new artist or title renames them all to "NNN - Artist - Title". With --only, '
                                   "only this file changes (a note on one version, say) and nothing is renamed.")
    p.add_argument("path", metavar="FILE", help="the song, or with --only any file")
    p.add_argument("--set", action="append", default=[], metavar="FIELD=VALUE",
                   help='a field and its value, e.g. --set "artist=Someone" (any field name; repeat it for more)')
    p.add_argument("--unset", action="append", default=[], metavar="FIELD", help="remove a field (repeat it for more)")
    p.add_argument("--only", action="store_true", help="change only this file, not the files made from the song")

    p = sub.add_parser("trim", help="cut a song's start or end (or add silence), with all its stems and versions",
                       description="Cuts the song's start and/or end (a video's intro or credits), or adds silence "
                                   "before or after it, in the song and everything made from it at once: its other "
                                   "formats, stems, transposed versions and clicks with the same cut, versions at "
                                   "another speed with the cut scaled. The practice click and the lyrics' times "
                                   "move along; takes recorded in REAPER are left alone (remake the song's REAPER "
                                   "project afterwards). Exact to the sample; compressed files are encoded again "
                                   "at a high quality. The old files go to the trash. Asks first unless --yes.")
    p.add_argument("path", metavar="FILE", help="the song, or any file made from it")
    p.add_argument("--start", metavar="TIME", help="keep from here: 12.5 (seconds) or 0:12.5 (default: the beginning)")
    p.add_argument("--end", metavar="TIME", help="keep up to here: 238 or 3:58 (default: the end)")
    p.add_argument("--pad-start", type=float, default=0.0, metavar="SECONDS", help="silence to add before, in seconds")
    p.add_argument("--pad-end", type=float, default=0.0, metavar="SECONDS", help="silence to add after, in seconds")
    p.add_argument("--yes", action="store_true", help="don't ask for confirmation")

    p = sub.add_parser("delete", help="send songs or single files to the trash",
                       description="Sends files to the system's trash (the Recycle Bin on WSL, for files on a "
                                   "Windows drive). A song goes with everything made from it (its other formats, "
                                   "stems, versions and clicks) and its lines in key.txt, bpm.txt and click.txt, and "
                                   "leaves its playlist's archive, so looking for new songs downloads it again. A "
                                   "stem or a version goes alone; --file deletes any single file alone, like an "
                                   ".mp3 copy. Asks first unless --yes.")
    p.add_argument("paths", nargs="*", metavar="SONG", help="songs to delete with everything made from them")
    p.add_argument("--file", action="append", default=[], metavar="FILE", help="a single file, alone (repeatable)")
    p.add_argument("--yes", action="store_true", help="don't ask for confirmation")

    p = sub.add_parser("archives", help="list the playlists downloaded so far, or forget them",
                       description="Lists each playlist downloaded so far, how many songs and where its folder "
                                   "is. --update looks for songs added to them and downloads only those. --move "
                                   "takes one to another folder. --add takes playlists from a folder copied from another computer or kept in a synced drive: each playlist's folder carries its record. --delete forgets some of them (by the numbers in "
                                   "the list) or all, so downloading them again gets every song again. Downloaded "
                                   "songs are never deleted.")
    p.add_argument("--delete", nargs="+", metavar="N", help='numbers from the list, or "all"')
    p.add_argument("--update", nargs="+", metavar="N",
                   help='look for new songs in playlists (numbers from the list, or "all") and download them')
    p.add_argument("--move", nargs=2, metavar=("N", "FOLDER"),
                   help="move playlist N (songs, stems and all) into FOLDER and keep downloading there; if you "
                        "moved it by hand already, records where it is now")
    p.add_argument("--add", metavar="FOLDER",
                   help="show FOLDER in the library (a synced drive, a folder copied from another computer) "
                        "and take the playlists recorded in it or in the folders inside it")
    p.add_argument("--yes", action="store_true", help="don't ask for confirmation")

    p = sub.add_parser("list", help="list the songs in the music folder (and wherever downloads went)",
                       description="What the interface's library shows: each folder with its songs, their key, "
                                   "tempo and click settings if detected, and how many files were made from each "
                                   "(stems, versions, copies, clicks). Folders outside the music folder where "
                                   "downloads went are included.")
    p.add_argument("text", nargs="?", metavar="TEXT", help="only songs (or folders) whose name has this")
    p.add_argument("--files", action="store_true", help="also list the files made from each song")

    p = sub.add_parser("open", help="open a folder in the file manager (the music folder by default)",
                       description="Opens the music folder, or the folder given (or the folder of the file "
                                   "given), in Explorer on WSL, the Finder on a Mac or the desktop's file manager.")
    p.add_argument("path", nargs="?", metavar="FOLDER|FILE")

    p = sub.add_parser("ui", help="open the interface in the browser (same commands, without the terminal)",
                       description="Starts a local server (only reachable from this computer) in the background "
                                   "and opens the interface in the browser; on WSL, the Windows browser. The "
                                   "terminal stays free; running it again opens the same interface. --stop "
                                   "closes it.")
    p.add_argument("--port", type=int, default=8765, help="local port (default: 8765, or the next free one)")
    p.add_argument("--no-browser", action="store_true", help="don't open the browser, just print the link")
    p.add_argument("--practice", metavar="FILE", help="open straight into the practice player with this song")
    p.add_argument("--stop", action="store_true", help="close the interface running in the background")
    p.add_argument("--restart", action="store_true",
                   help="close it and open it again (after an upgrade, or if it misbehaves)")
    p.add_argument("--yes", action="store_true", help="with --stop or --restart: close it even if something is running")
    p.add_argument("--foreground", action="store_true",
                   help="keep it in this terminal instead (Ctrl+C closes it), like before")

    p = sub.add_parser("lyrics", help="find the lyrics of songs and save them next to each song",
                       description="Looks up each song's lyrics in an open lyrics database, by its name "
                                   '("Artist - Song") and length, and saves them as "<song>.lyrics.json". '
                                   "Highlighting and notes are done in the interface (song-wizard ui).")
    p.add_argument("paths", nargs="+", metavar="FILE|FOLDER")
    p.add_argument("--from", dest="text_from", metavar="FILE",
                   help="don't look them up: take them from a text file (- reads what you paste, Ctrl+D to end)")
    p.add_argument("--force", action="store_true", help="look them up again (highlights and notes are lost)")
    p.add_argument("--export", action="store_true",
                   help='save the lyrics with highlights and notes as "<song>.lyrics.html", to print or share')
    what = p.add_mutually_exclusive_group()
    what.add_argument("--chords", action="store_true",
                      help='with --export: the chords over the words, as "<song>.chords.html" (needs song-wizard chords; '
                           "without timed lyrics, in rows of bars)")
    what.add_argument("--bass", action="store_true",
                      help='with --export: the bass\'s notes over the words, as "<song>.bass.html" (needs song-wizard notes)')
    p.add_argument("--shift", type=int, default=0, choices=range(-6, 7), metavar="N",
                   help="with --chords or --bass: names moved N semitones (-6 to 6), like the practice player's pitch")
    p.add_argument("--simple", action="store_true", help="with --chords: only major or minor (A7 -> A, C#m7 -> C#m)")
    p.add_argument("--bars", type=int, default=4, choices=(2, 4), help="bars per row where nobody sings (2 or 4; default 4)")

    p = sub.add_parser("setlist", help="a printable setlist of a folder, or of songs from any folders",
                       description="Lists songs with their key and tempo (from key.txt and bpm.txt: run key "
                                   "and bpm first) and length, and the total. Of one folder: in the order of "
                                   "its files (001 - ...), saved as Setlist.txt and Setlist.html (one A4 page, "
                                   "to print) in the folder. Of songs: in the order given, from any folders; "
                                   "nothing is saved in them (--out saves the page).")
    p.add_argument("paths", nargs="*", metavar="FOLDER|SONG", help="a folder (default: the current one), or songs")
    p.add_argument("--title", help="title on top (default: the playlist's or the folder's name; for songs, Setlist)")
    p.add_argument("--lyrics", action="store_true",
                   help="add the lyrics of the songs that have them, with their marks, one per page after the list")
    p.add_argument("--chords", action="store_true",
                   help="with --lyrics: the chords over the words, for the songs that have them (songs with chords "
                        "but no lyrics get their chords in rows of bars)")
    p.add_argument("--simple", action="store_true", help="with --chords: only major or minor")
    p.add_argument("--bars", type=int, default=4, choices=(2, 4), help="with --chords: bars per row where nobody sings")
    p.add_argument("--out", metavar="FILE.html", help="save the page here (for a folder: instead of in it)")

    p = sub.add_parser("order", help="put a folder's songs in another order (renumbering their files)",
                       description="Numbers the folder's songs (001 - ...) in the order given: each song's "
                                   "stems, versions, results, lyrics and REAPER project follow it. Songs not "
                                   "given go after, in the order they had. Songs added by hand to a playlist's "
                                   "folder get the number after the last one on their own, and new downloads go "
                                   "on from there.")
    p.add_argument("folder", metavar="FOLDER")
    p.add_argument("songs", nargs="+", metavar="SONG", help="songs of the folder (paths or file names), in their new order")

    p = sub.add_parser("reaper", help="open the song's REAPER project, making it first if there's none",
                       description='Opens "<song>.rpp" (next to the song) in REAPER. If there\'s none, makes it '
                                   "first: a track per stem (the set the practice player starts with playing, the "
                                   "other stems and the song itself muted), the tempo and meter of the practice "
                                   "click with the song's first beat on a bar line, REAPER's own click, and a "
                                   'track armed to record. Takes are named "<song> (record <date> <time>).wav" '
                                   "so they go with their song: that's a REAPER setting for all projects, set in "
                                   "reaper.ini when REAPER is closed (a copy of it is kept). An existing project "
                                   "is never rewritten, unless --redo.")
    p.add_argument("path", nargs="?", metavar="FILE", help="the song, or any file made from it")
    p.add_argument("--setting", choices=["show", "restore", "apply"],
                   help="the recorded takes' names setting song-wizard changes in REAPER: show it, put it back as "
                        "it was (and don't change it again), or let song-wizard set it again")
    p.add_argument("--redo", action="store_true",
                   help="send the existing project to the trash and make a new one (e.g. after separating stems)")
    p.add_argument("--no-open", action="store_true", help="just make it, don't open REAPER")
    p.add_argument("--yes", action="store_true", help="with --redo: don't ask for confirmation")

    p = sub.add_parser("report", help="put together a report to ask for help when something fails",
                       description="Writes a text file with this computer's setup and the last lines of "
                                   "song-wizard's log (your home folder shows as ~), and opens a GitHub issue "
                                   "already filled in to attach it to. Without a GitHub account, send the file "
                                   "to whoever helps you with song-wizard.")
    p.add_argument("--yes", action="store_true", help="open the folder and the GitHub form without asking")

    sub.add_parser("config", help="show the settings file and the values in use (creates it if missing)")
    sub.add_parser("setup", help="check dependencies and show how to install what's missing")
    p = sub.add_parser("uninstall", help="remove song-wizard and what it keeps outside the music folder",
                       description="Shows what goes and how much it takes, asks, and removes the separation "
                                   "models, the record of downloads, the logs, the settings and song-wizard itself "
                                   "(uv tool uninstall). Your music isn't touched, nor ffmpeg, rubberband, deno, uv "
                                   "or uv's download cache. If song-wizard changed REAPER's takes setting, it offers "
                                   "to put it back.")
    p.add_argument("--keep-data", action="store_true",
                   help="remove only the program: keep the models, the record of downloads and the settings")
    p.add_argument("--yes", action="store_true", help="don't ask")
    p = sub.add_parser("upgrade", help="update song-wizard and everything it uses (yt-dlp included)",
                       description="Installs the newest published version of song-wizard (each one is a vX.Y.Z "
                                   "tag on GitHub) if there's a newer one, and the newest of what it uses (yt-dlp "
                                   "above all). --list shows the published versions; --to installs a given one, "
                                   "older ones included. Versions retired for a bad bug (retired.txt on GitHub) "
                                   "aren't offered, and whoever has one is moved off it.")
    which = p.add_mutually_exclusive_group()
    which.add_argument("--check", action="store_true", help="only tell whether there's a newer song-wizard")
    which.add_argument("--list", action="store_true", help="list the published versions")
    which.add_argument("--to", metavar="VERSION", help="install this version (e.g. 0.12.0), newer or older")
    p.add_argument("--all", action="store_true", help="with --list: also the retired versions, with why")
    p.add_argument("--force", action="store_true", help="with --to: install it even if it was retired")
    return parser


def main(argv=None):
    from . import log

    log.start(sys.argv[1:] if argv is None else argv)
    started = time.monotonic()
    try:
        dispatch(argv)
    except SystemExit as e:
        log.finished(e.code, started)
        raise
    except KeyboardInterrupt:
        log.info("interrupted after %.1f s", time.monotonic() - started)
        raise
    except BaseException:
        log.crashed(started)
        raise
    else:
        log.finished(0, started)


def dispatch(argv):
    parser = build_parser()
    args = parser.parse_args(argv)
    from . import config
    config.ensure()  # the settings file is always there to look at and change

    if args.command == "download":
        from . import download, system
        download.run(args.url, wav=args.wav, extra=args.ytdlp_args,
                     to=system.local_path(args.to) if args.to else None)
    elif args.command == "key":
        from . import key
        key.run(args.paths, value=args.set, force=args.force)
    elif args.command == "bpm":
        from . import bpm
        bpm.run(args.paths, value=args.set, force=args.force)
    elif args.command == "convert":
        from . import convert
        convert.run(args.paths, fmt=args.format, overwrite=args.overwrite)
    elif args.command == "delete":
        from . import delete
        delete.run(songs=args.paths, files=args.file, yes=args.yes)
    elif args.command == "trim":
        from . import trim
        trim.run(args.path, start=args.start, end=args.end, pad_start=args.pad_start, pad_end=args.pad_end,
                 yes=args.yes)
    elif args.command == "tag":
        from . import tags
        tags.run(args.path, args.set, args.unset, only=args.only)
    elif args.command == "rename":
        from . import rename
        rename.run(args.path, args.name)
    elif args.command == "archives":
        from . import archives, system
        if args.update:
            archives.update(args.update)
        elif args.move:
            archives.move(args.move[0], system.local_path(args.move[1]))
        elif args.add:
            archives.add(system.local_path(args.add))
        elif args.delete:
            archives.delete(args.delete, yes=args.yes)
        else:
            archives.show()
    elif args.command == "ui":
        from . import ui
        if args.stop:
            ui.stop(yes=args.yes)
        elif args.restart:
            if ui.stop(yes=args.yes):
                ui.run(port=args.port, open_page=not args.no_browser, practice=args.practice)
        else:
            ui.run(port=args.port, open_page=not args.no_browser, practice=args.practice,
                   foreground=args.foreground)
    elif args.command == "lyrics":
        from . import lyrics
        if (args.chords or args.bass or args.shift or args.simple) and not args.export:
            sys.exit("song-wizard lyrics: --chords, --bass, --shift and --simple go with --export.")
        kind = "chords" if args.chords else "bass" if args.bass else "lyrics"
        lyrics.run(args.paths, text_from=args.text_from, force=args.force, export_page=args.export,
                   kind=kind, shift=args.shift, simple=args.simple, bars=args.bars)
    elif args.command == "setlist":
        from . import setlist
        if args.chords and not args.lyrics:
            sys.exit("song-wizard setlist: --chords goes with --lyrics.")
        setlist.run(args.paths, name=args.title, with_lyrics=args.lyrics, out=args.out,
                    with_chords=args.chords, simple=args.simple, bars=args.bars)
    elif args.command == "order":
        from . import numbering, system
        numbering.reorder(system.local_path(args.folder), args.songs)
    elif args.command == "reaper":
        from . import reaper
        if args.setting:
            reaper.run_setting(args.setting)
        elif args.path:
            reaper.run(args.path, redo=args.redo, yes=args.yes, open_it=not args.no_open)
        else:
            sys.exit("song-wizard reaper: give a song, or --setting.")
    elif args.command == "report":
        from . import report
        report.run(yes=args.yes)
    elif args.command == "list":
        from . import listing
        listing.run(args.text, files=args.files)
    elif args.command == "open":
        from . import system
        from .paths import music_dir
        target = Path(system.local_path(args.path)) if args.path else music_dir()
        if target.is_file():
            target = target.parent
        if not target.is_dir():
            sys.exit(f"{target}: no such folder.")
        if not system.open_folder(target):
            sys.exit("No file manager found on this system.")
        print(f"Opened {system.shown_path(target)}")
    elif args.command == "config":
        from . import config
        config.show()
    elif args.command == "click":
        from . import click
        click.run(args.bpm, meter=args.meter, duration=args.duration, bars=args.bars, like=args.like,
                  subdivide=args.subdivide, output=args.output, song=args.song)
    elif args.command == "notes":
        from . import notes
        notes.run(args.paths, part=args.part, force=args.force)
    elif args.command == "drums":
        from . import drums
        if args.full and not args.sheet:
            sys.exit("song-wizard drums: --full goes with --sheet.")
        drums.run(args.paths, force=args.force, accept=args.accept_model_license, sheet=args.sheet,
                  as_midi=args.midi, full=args.full)
    elif args.command == "chords":
        from . import chords
        chords.run(args.paths, force=args.force)
    elif args.command == "align":
        from . import align
        align.run(args.paths, bpm=args.bpm, meter=args.meter, first=args.first)
    elif args.command == "transpose":
        from . import transpose
        transpose.run(args.semitones, args.paths)
    elif args.command == "speed":
        from . import speed
        speed.run(args.percent, args.paths, semitones=args.semitones)
    elif args.command == "separate":
        from . import separate
        separate.run(args.stem, args.paths, force_cpu=args.cpu)
    elif args.command == "setup":
        from . import setup
        setup.run()
    elif args.command == "uninstall":
        from . import uninstall
        uninstall.run(keep_data=args.keep_data, yes=args.yes)
    elif args.command == "upgrade" and (args.check or args.list):
        from . import updates
        updates.check() if args.check else updates.show(everything=args.all)
    elif args.command == "upgrade":
        # Everything this needs is loaded before the install replaces the files: importing one
        # afterwards would mix this version's modules, already in memory, with the new ones
        # (0.6.0 → 0.15.0 failed that way, after a good install).
        from . import ui, updates
        code = updates.to(args.to, force=args.force) if args.to else updates.upgrade()
        if code == 0 and ui.running():
            print("The interface is still running the version from before: song-wizard ui --restart "
                  "opens the new one.")
        sys.exit(code)
    else:
        parser.print_help()
        sys.exit(1)
