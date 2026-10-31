import os
import re
import shutil
import subprocess
import sys

from .audio import require_ffmpeg
from .paths import ARCHIVE_DIR, music_dir


def node_ok():
    """Node works as yt-dlp's JS runtime only at v20 or newer (deno is picked up on its own)."""
    if not shutil.which("node"):
        return False
    version = subprocess.run(["node", "-v"], capture_output=True, text=True).stdout
    match = re.match(r"v(\d+)", version)
    return bool(match) and int(match.group(1)) >= 20


def run(url, wav=False, extra=()):
    require_ffmpeg()
    # One archive per playlist, so a song downloaded for one show isn't skipped for another.
    match = re.search(r"[?&]list=([A-Za-z0-9_-]+)", url)
    archive = ARCHIVE_DIR / f"{match.group(1) if match else 'singles'}.txt"
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)

    dest = music_dir()
    args = [
        sys.executable, "-m", "yt_dlp",
        "-f", "bestaudio[acodec=opus]/bestaudio",
        "-x",
        "--windows-filenames",
        "--embed-metadata",
        "--download-archive", str(archive),
        "-o", f"{dest}/%(playlist_title|Singles)s/%(playlist_index&{{:03d}} - |)s%(title)s.%(ext)s",
    ]
    if node_ok():
        args += ["--js-runtimes", "node"]
    if wav:
        args += ["--exec", 'f=%(filepath)q; ffmpeg -nostdin -n -loglevel error -i "$f" "${f%.*}.wav"']
    args += [*extra, url]
    os.execv(sys.executable, args)
