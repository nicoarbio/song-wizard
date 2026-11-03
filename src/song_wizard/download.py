import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from . import archives
from .audio import require_ffmpeg
from .paths import music_dir


def node_ok():
    """Node works as yt-dlp's JS runtime only at v20 or newer (deno is picked up on its own)."""
    if not shutil.which("node"):
        return False
    version = subprocess.run(["node", "-v"], capture_output=True, text=True).stdout
    match = re.match(r"v(\d+)", version)
    return bool(match) and int(match.group(1)) >= 20


def name_by_data(path):
    from . import rename, tags
    from .audio import base_of

    new = tags.name_for(tags.read(path))
    current = base_of(Path(path).name)
    number = re.match(r"^\d+ - ", current)
    target = (number.group(0) if number else "") + new if new else current
    if target != current:
        try:
            rename.run(path, new)
        except SystemExit as e:
            print(f"  {Path(path).name}: kept its name ({e.code})")
            target = current
    # song-wizard's mark on what it downloaded (and the .wav made from it).
    final = Path(path).with_name(target + Path(path).suffix)
    if final.is_file():
        for f in tags.song_files(final):
            tags.stamp(f, f)


def run(url, wav=False, extra=(), to=None):
    sys.exit(fetch(url, wav=wav, extra=extra, to=to))


def fetch(url, wav=False, extra=(), to=None):
    """to: the folder where a new playlist's folder (or Singles) goes; the music folder if not
    given. A playlist downloaded before goes on in its own folder, wherever it is now."""
    require_ffmpeg()
    # One archive per playlist, so a song downloaded for one show isn't skipped for another.
    match = re.search(r"[?&]list=([A-Za-z0-9_-]+)", url)
    archive_id = match.group(1) if match else archives.SINGLES
    archive = archives.ARCHIVE_DIR / f"{archive_id}.txt"
    archives.ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    # yt-dlp writes the playlist's name here once it's done, for "song-wizard archives".
    title_file = Path(tempfile.mkstemp(prefix="song-wizard-", suffix=".txt")[1])
    # And the path of each song once it's in place, to remember the playlist's folder.
    files_file = Path(tempfile.mkstemp(prefix="song-wizard-", suffix=".txt")[1])

    # yt-dlp reads "%" in the output path as a template field.
    escape = lambda path: str(path).replace("%", "%%")
    song = "%(playlist_index&{:03d} - |)s%(title)s.%(ext)s"
    known = archives.read_meta(archive_id).get("folder") if archive_id != archives.SINGLES else None
    if known and Path(known).is_dir():
        # Another computer may have downloaded more songs into it (a synced folder): its record says.
        archives.adopt(known)
    if to is None and known and Path(known).is_dir():
        output = f"{escape(known)}/{song}"
    else:
        from . import system

        if to and (letter := system.unmounted_drive(to)):
            sys.exit(system.mount_hint(letter))
        dest = Path(to).expanduser() if to else music_dir()
        output = f"{escape(dest)}/%(playlist_title|Singles)s/{song}"
    args = [
        sys.executable, "-m", "yt_dlp",
        "-f", "bestaudio[acodec=opus]/bestaudio",
        "-x",
        "--windows-filenames",
        "--embed-metadata",
        "--download-archive", str(archive),
        "--print-to-file", "playlist:%(title)s", str(title_file),
        "--print-to-file", "after_move:%(filepath)s", str(files_file),
        "-o", output,
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
        files = [l for l in files_file.read_text(errors="replace").splitlines() if l.strip()]
        title_file.unlink(missing_ok=True)
        files_file.unlink(missing_ok=True)
    # Named by its data, "001 - Artist - Title", as the song's data window names it: what the
    # site put there (often the uploader as the artist) shows up front, to be corrected by hand.
    for path in files:
        name_by_data(path)
    if archive.exists():
        archives.remember(archive_id, url, lines[-1] if lines else None,
                          folder=str(Path(files[-1]).parent) if files else None, wav=wav)
    return code
