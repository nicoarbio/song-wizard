import argparse
import shutil
import subprocess
import sys

from . import __version__

DESCRIPTION = "Prepare songs for band practice: download, key detection, transposition and stem separation."

EPILOG = """\
examples:
  song-wizard download "https://www.youtube.com/playlist?list=..."
  song-wizard key ~/Music/Show
  song-wizard transpose -2 "song.opus"
  song-wizard separate --stem drums ~/Music/Show
  song-wizard separate --stem vocals --stem guitar "song.opus"

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

    p = sub.add_parser("transpose", help="shift songs up or down by semitones",
                       description='Shift pitch without changing tempo or timing. Writes "Title (+2).wav" '
                                   "(32-bit float) next to the original.")
    p.add_argument("semitones", type=float, metavar="N",
                   help="semitones: +1 = half step up, +2 = whole step up, -1.5, ...")
    p.add_argument("paths", nargs="+", metavar="FILE|FOLDER")

    from .separate import STEMS
    p = sub.add_parser("separate", help="split out instruments: the instrument alone plus everything else",
                       description='For each --stem, writes "Title (drums).wav" (the instrument alone) and '
                                   '"Title (no drums).wav" (everything else) next to the original, as 44.1 kHz '
                                   "32-bit float WAV. The two always add up to the exact original. Models are "
                                   "downloaded the first time they are used. Runs on an NVIDIA GPU (GTX 16 / "
                                   "RTX 20 or newer) or an Apple Silicon GPU when available, else on the CPU.")
    p.add_argument("--stem", action="append", required=True, choices=STEMS,
                   help="instrument to separate; repeat for several")
    p.add_argument("--cpu", action="store_true",
                   help="use the CPU even if a GPU is available (slower, but avoids GPU problems)")
    p.add_argument("paths", nargs="+", metavar="FILE|FOLDER")

    sub.add_parser("setup", help="check dependencies and show how to install what's missing")
    sub.add_parser("upgrade", help="update song-wizard and everything it uses (yt-dlp included)")

    args = parser.parse_args()

    if args.command == "download":
        from . import download
        download.run(args.url, wav=args.wav, extra=args.ytdlp_args)
    elif args.command == "key":
        from . import key
        key.run(args.paths)
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
