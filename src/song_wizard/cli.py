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
  song-wizard click --count-in 2 "song.opus"
  song-wizard transpose -2 "song.opus"
  song-wizard separate --stem drums ~/Music/Show
  song-wizard separate --stem vocals --stem guitar "song.opus"
  song-wizard separate --stem all "song.opus"

run "song-wizard COMMAND --help" for the options of each command.
"""


def main():
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

    p = sub.add_parser("click", help="(experimental) make a click track with a count-in, aligned to the song",
                       description='Experimental: the click follows the song closely, but the accented first beat of the bar can land on the wrong beat; check it and fix it with --shift. Writes "Title (click).wav". The count-in goes before bar 1, so a copy of the '
                                   'song with that much silence added, "Title (count-in).wav", starts together '
                                   'with the click; stems of the song next to it ("Title (drums).wav"...) get '
                                   'the same copy. By default the click follows the song, so it stays aligned '
                                   "even when the tempo drifts. Defaults for --meter and --count-in come from "
                                   'the settings file (see "song-wizard config").')
    p.add_argument("--meter", help='time signature, e.g. 4/4, 3/4, 6/8: the top number is the clicks per bar, '
                                   'the first one accented (default: 4/4)')
    p.add_argument("--count-in", type=int, metavar="BARS", help="bars of count-in; 0 for none (default: 1)")
    p.add_argument("--steady", action="store_true",
                   help="one fixed tempo for the whole song instead of following it")
    p.add_argument("--shift", type=int, default=0, metavar="N",
                   help="move the accented first beat of the bar N beats later (negative: earlier), "
                        "if it was detected on the wrong beat")
    p.add_argument("paths", nargs="+", metavar="FILE|FOLDER")

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

    sub.add_parser("config", help="show the settings file and the values in use (creates it if missing)")
    sub.add_parser("setup", help="check dependencies and show how to install what's missing")
    sub.add_parser("upgrade", help="update song-wizard and everything it uses (yt-dlp included)")

    args = parser.parse_args()

    if args.command == "download":
        from . import download
        download.run(args.url, wav=args.wav, extra=args.ytdlp_args)
    elif args.command == "key":
        from . import key
        key.run(args.paths)
    elif args.command == "bpm":
        from . import bpm
        bpm.run(args.paths)
    elif args.command == "click":
        from . import click, config
        settings = config.load()["click"]
        click.run(args.paths,
                  meter=args.meter or settings["meter"],
                  count_in=args.count_in if args.count_in is not None else int(settings["count_in"]),
                  steady=args.steady, shift=args.shift)
    elif args.command == "config":
        from . import config
        config.show()
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
