import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from . import archives
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
    archive_id = match.group(1) if match else archives.SINGLES
    archive = ARCHIVE_DIR / f"{archive_id}.txt"
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    # yt-dlp writes the playlist's name here once it's done, for "song-wizard archives".
    title_file = Path(tempfile.mkstemp(prefix="song-wizard-", suffix=".txt")[1])

    dest = music_dir()
    args = [
        sys.executable, "-m", "yt_dlp",
        "-f", "bestaudio[acodec=opus]/bestaudio",
        "-x",
        "--windows-filenames",
        "--embed-metadata",
        "--download-archive", str(archive),
        "--print-to-file", "playlist:%(title)s", str(title_file),
        "-o", f"{dest}/%(playlist_title|Singles)s/%(playlist_index&{{:03d}} - |)s%(title)s.%(ext)s",
    ]
    if node_ok():
        args += ["--js-runtimes", "node"]
    if wav:
        args += ["--exec", 'f=%(filepath)q; ffmpeg -nostdin -n -loglevel error -i "$f" "${f%.*}.wav"']
    args += [*extra, url]
    try:
        code = subprocess.run(args).returncode
    except KeyboardInterrupt:
        code = 130
    finally:
        lines = [l for l in title_file.read_text(errors="replace").splitlines() if l.strip()]
        title_file.unlink(missing_ok=True)
    if archive.exists():
        archives.remember(archive_id, url, lines[-1] if lines else None)
    sys.exit(code)
