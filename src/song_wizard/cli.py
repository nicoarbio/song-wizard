import argparse
import shutil
import subprocess
import sys

from . import __version__

DESCRIPTION = ("Prepare songs for band practice: download, key and tempo detection, click tracks, "
               "transposition and stem separation.")

EPILOG = """\
examples:
  song-wizard download "https://www.youtube.com/playlist?list=..."
  song-wizard key ~/Music/Show
  song-wizard bpm ~/Music/Show
  song-wizard click 120 --duration 4:30
  song-wizard transpose -2 "song.opus"
  song-wizard separate --stem drums ~/Music/Show
  song-wizard separate --stem vocals --stem guitar "song.opus"
  song-wizard separate --stem all "song.opus"
  song-wizard convert "song (no drums).wav"
  song-wizard ui

run "song-wizard COMMAND --help" for the options of each command.
"""


def build_parser():
    parser = argparse.ArgumentParser(prog="song-wizard", description=DESCRIPTION, epilog=EPILOG,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", metavar="COMMAND")

    p = sub.add_parser("download", help="download audio from YouTube as original Opus (no re-encoding)",
                       description="Download a video or playlist as original Opus, without re-encoding. "
                                   "Playlists go to <Music>/<playlist name>/001 - Title.opus, single videos "
                                   "to <Music>/Singles/. <Music> is $SONG_WIZARD_DIR if set, else your Music "
                                   "folder (the Windows one on WSL). An archive per playlist is kept: running "
                                   "it again only downloads new songs.")
    p.add_argument("--wav", action="store_true", help="also write a .wav next to each .opus")
    p.add_argument("url", help="video or playlist URL")
    p.add_argument("ytdlp_args", nargs=argparse.REMAINDER, metavar="...",
                   help="extra yt-dlp options, e.g. --cookies-from-browser chrome")

    p = sub.add_parser("key", help="detect the key of songs",
                       description="Detect the key of each song. 4/4 means all four detection methods agree; "
                                   "lower counts are worth checking by ear. The most common mix-up is with "
                                   "the relative key, which is always shown.")
    p.add_argument("paths", nargs="+", metavar="FILE|FOLDER")

    p = sub.add_parser("bpm", help="detect the tempo of songs",
                       description="Detect the tempo of each song and how steady it is. Songs recorded without "
                                   "a click drift, so a range is shown instead. Like any tempo detector it can "
                                   "land on half or double the real tempo; uncertain results say so.")
    p.add_argument("paths", nargs="+", metavar="FILE|FOLDER")

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
    length.add_argument("--like", metavar="FILE", help="as long as this song")
    p.add_argument("--subdivide", type=int, default=1, metavar="N",
                   help="softer clicks between beats: 2 = eighths, 3 = triplets, 4 = sixteenths")
    p.add_argument("-o", "--output", metavar="PATH", help="output file or folder")

    p = sub.add_parser("transpose", help="shift songs up or down by semitones",
                       description='Shift pitch without changing tempo or timing. Writes "Title (+2).wav" '
                                   "(32-bit float) next to the original.")
    p.add_argument("semitones", type=float, metavar="N",
                   help="semitones: +1 = half step up, +2 = whole step up, -1.5, ...")
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

    p = sub.add_parser("archives", help="list the playlists downloaded so far, or forget them",
                       description="Lists each playlist downloaded so far and how many songs. --delete forgets "
                                   "some of them (by the numbers in the list) or all, so downloading them "
                                   "again gets every song again. Downloaded songs are never deleted.")
    p.add_argument("--delete", nargs="+", metavar="N", help='numbers from the list, or "all"')
    p.add_argument("--yes", action="store_true", help="don't ask for confirmation")

    p = sub.add_parser("ui", help="open the interface in the browser (same commands, without the terminal)",
                       description="Starts a local server (only reachable from this computer) and opens the "
                                   "interface in the browser; on WSL, the Windows browser. Keep the terminal "
                                   "open while using it; Ctrl+C closes it.")
    p.add_argument("--port", type=int, default=8765, help="local port (default: 8765, or the next free one)")
    p.add_argument("--no-browser", action="store_true", help="don't open the browser, just print the link")

    sub.add_parser("config", help="show the settings file and the values in use (creates it if missing)")
    sub.add_parser("setup", help="check dependencies and show how to install what's missing")
    sub.add_parser("upgrade", help="update song-wizard and everything it uses (yt-dlp included)")
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "download":
        from . import download
        download.run(args.url, wav=args.wav, extra=args.ytdlp_args)
    elif args.command == "key":
        from . import key
        key.run(args.paths)
    elif args.command == "bpm":
        from . import bpm
        bpm.run(args.paths)
    elif args.command == "convert":
        from . import convert
        convert.run(args.paths, fmt=args.format, overwrite=args.overwrite)
    elif args.command == "archives":
        from . import archives
        if args.delete:
            archives.delete(args.delete, yes=args.yes)
        else:
            archives.show()
    elif args.command == "ui":
        from . import ui
        ui.run(port=args.port, open_page=not args.no_browser)
    elif args.command == "config":
        from . import config
        config.show()
    elif args.command == "click":
        from . import click
        click.run(args.bpm, meter=args.meter, duration=args.duration, bars=args.bars, like=args.like,
                  subdivide=args.subdivide, output=args.output)
    elif args.command == "transpose":
        from . import transpose
        transpose.run(args.semitones, args.paths)
    elif args.command == "separate":
        from . import separate
        separate.run(args.stem, args.paths, force_cpu=args.cpu)
    elif args.command == "setup":
        from . import setup
        setup.run()
    elif args.command == "upgrade":
        if not shutil.which("uv"):
            sys.exit("uv is missing; reinstall song-wizard following the README.")
        sys.exit(subprocess.run(["uv", "tool", "upgrade", "song-wizard"]).returncode)
    else:
        parser.print_help()
        sys.exit(1)
