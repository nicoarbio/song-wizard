import argparse
from pathlib import Path
import shutil
import subprocess
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
  song-wizard convert "song (no drums).wav"
  song-wizard rename "001 - Song (Official Video).opus" "Song"
  song-wizard delete "001 - Song.opus"
  song-wizard list cryin --files
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
                                   "name>/001 - Title.opus, single songs "
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

    p = sub.add_parser("transpose", help="shift songs up or down by semitones",
                       description='Shift pitch without changing tempo or timing. Writes "Title (+2).wav" '
                                   "(32-bit float) next to the original.")
    p.add_argument("semitones", type=float, metavar="N",
                   help="semitones: +1 = half step up, +2 = whole step up, -1.5, ...")
    p.add_argument("paths", nargs="+", metavar="FILE|FOLDER")

    p = sub.add_parser("speed", help="slow songs down or speed them up without changing the pitch",
                       description='Change the speed without changing the pitch. Writes "Title (80%%).wav" '
                                   "(32-bit float) next to the original; with --semitones, also shifts the "
                                   'pitch in the same pass: "Title (80%%, -2).wav".')
    p.add_argument("percent", type=float, metavar="PERCENT",
                   help="speed in percent of the original: 80 = slower, 120 = faster (25 to 200)")
    p.add_argument("--semitones", type=float, default=0, metavar="N", help="also shift the pitch, like transpose")
    p.add_argument("paths", nargs="+", metavar="FILE|FOLDER")

    from .separate import ALL, STEMS
    p = sub.add_parser("separate", help="split out instruments: the instrument alone plus everything else",
                       description='For each --stem, writes "Title (drums).wav" (the instrument alone) and '
                                   '"Title (no drums).wav" (everything else) next to the original, as 44.1 kHz '
                                   "32-bit float WAV. The two always add up to the exact original. Models are "
                                   "downloaded the first time they are used. Runs on an NVIDIA GPU (GTX 16 / "
                                   "RTX 20 or newer) or an Apple Silicon GPU when available, else on the CPU.")
    p.add_argument("--stem", action="append", required=True, choices=[*STEMS, ALL],
                   help='instrument to separate; repeat for several. "all" writes the four '
                        'instruments plus "Title (other).wav" (everything else: keys, synths, '
                        'backing vocals...), without the "no X" files; the five add up to the original')
    p.add_argument("--cpu", action="store_true",
                   help="use the CPU even if a GPU is available (slower, but avoids GPU problems)")
    p.add_argument("paths", nargs="+", metavar="FILE|FOLDER")

    from .convert import FORMATS
    p = sub.add_parser("convert", help="convert to MP3 (or M4A) to share, e.g. over WhatsApp",
                       description="Converts to a small format any phone plays: MP3 at ~190 kbps by default "
                                   '(about 7 MB for 5 minutes), or M4A (AAC). Writes "Title.mp3" next to each '
                                   "file. Given a folder, only lossless files (WAV, FLAC, AIFF) are converted; "
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
                                   "takes one to another folder. --delete forgets some of them (by the numbers in "
                                   "the list) or all, so downloading them again gets every song again. Downloaded "
                                   "songs are never deleted.")
    p.add_argument("--delete", nargs="+", metavar="N", help='numbers from the list, or "all"')
    p.add_argument("--update", nargs="+", metavar="N",
                   help='look for new songs in playlists (numbers from the list, or "all") and download them')
    p.add_argument("--move", nargs=2, metavar=("N", "FOLDER"),
                   help="move playlist N (songs, stems and all) into FOLDER and keep downloading there; if you "
                        "moved it by hand already, records where it is now")
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
    p.add_argument("--yes", action="store_true", help="with --stop: close it even if something is running")
    p.add_argument("--foreground", action="store_true",
                   help="keep it in this terminal instead (Ctrl+C closes it), like before")

    p = sub.add_parser("setlist", help="a printable setlist of a folder: key, tempo and length of each song",
                       description="Lists the songs of a folder in the order of their files (001 - ...), with "
                                   "key and tempo (from key.txt and bpm.txt: run key and bpm first) and length, "
                                   "and saves Setlist.txt and Setlist.html (one A4 page, to print) in the folder.")
    p.add_argument("folder", nargs="?", default=".", help="the folder (default: the current one)")
    p.add_argument("--title", help="title on top (default: the playlist's or the folder's name)")

    p = sub.add_parser("report", help="put together a report to ask for help when something fails",
                       description="Writes a text file with this computer's setup and the last lines of "
                                   "song-wizard's log (your home folder shows as ~), and opens a GitHub issue "
                                   "already filled in to attach it to. Without a GitHub account, send the file "
                                   "to whoever helps you with song-wizard.")
    p.add_argument("--yes", action="store_true", help="open the folder and the GitHub form without asking")

    sub.add_parser("config", help="show the settings file and the values in use (creates it if missing)")
    sub.add_parser("setup", help="check dependencies and show how to install what's missing")
    sub.add_parser("upgrade", help="update song-wizard and everything it uses (yt-dlp included)")
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
    elif args.command == "rename":
        from . import rename
        rename.run(args.path, args.name)
    elif args.command == "archives":
        from . import archives, system
        if args.update:
            archives.update(args.update)
        elif args.move:
            archives.move(args.move[0], system.local_path(args.move[1]))
        elif args.delete:
            archives.delete(args.delete, yes=args.yes)
        else:
            archives.show()
    elif args.command == "ui":
        from . import ui
        if args.stop:
            ui.stop(yes=args.yes)
        else:
            ui.run(port=args.port, open_page=not args.no_browser, practice=args.practice,
                   foreground=args.foreground)
    elif args.command == "setlist":
        from . import setlist
        setlist.run(args.folder, name=args.title)
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
    elif args.command == "upgrade":
        if not shutil.which("uv"):
            sys.exit("uv is missing; reinstall song-wizard following the README.")
        code = subprocess.run(["uv", "tool", "upgrade", "song-wizard"]).returncode
        from . import ui
        if code == 0 and ui.running():
            print("The interface is still running the version from before: close it with "
                  "song-wizard ui --stop and open it again with song-wizard ui.")
        sys.exit(code)
    else:
        parser.print_help()
        sys.exit(1)
