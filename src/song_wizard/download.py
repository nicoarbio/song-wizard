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
    from . import numbering

    numbering.name(path)


def run(url, wav=False, extra=(), to=None, decide=()):
    sys.exit(fetch(url, wav=wav, extra=extra, to=to, decide=decide))


# yt-dlp reads "%" in the output path as a template field.
escape = lambda path: str(path).replace("%", "%%")
SONG = "%(playlist_index&{:03d} - |)s%(title)s.%(ext)s"


def where(url, to=None):
    """(archive id, the playlist's folder if it was downloaded before, yt-dlp's output template).
    to: where a new playlist's folder (or Singles) goes; the music folder if not given."""
    # One archive per playlist, so a song downloaded for one show isn't skipped for another.
    match = re.search(r"[?&]list=([A-Za-z0-9_-]+)", url)
    archive_id = match.group(1) if match else archives.SINGLES
    known = archives.read_meta(archive_id).get("folder") if archive_id != archives.SINGLES else None
    known = known if known and Path(known).is_dir() else None
    if to is None and known:
        return archive_id, known, f"{escape(known)}/{SONG}"
    from . import system

    if to and (letter := system.unmounted_drive(to)):
        sys.exit(system.mount_hint(letter))
    dest = Path(to).expanduser() if to else music_dir()
    return archive_id, known, f"{escape(dest)}/%(playlist_title|Singles)s/{SONG}"


def fetch(url, wav=False, extra=(), to=None, decide=()):
    """to: the folder where a new playlist's folder (or Singles) goes; the music folder if not
    given. A playlist downloaded before goes on in its own folder, wherever it is now. First the
    playlist is gone over (review.py): songs that left it go to Singles, and what to do with the
    ones already here elsewhere is asked (or given with decide: ["VIDEO_ID=copy", ...])."""
    from . import layout, numbering, review
    from .song import old_layout_message

    require_ffmpeg()
    archive_id, known, output = where(url, to)
    archive = archives.ARCHIVE_DIR / f"{archive_id}.txt"
    archives.ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    if known:
        if layout.needed(known):
            sys.exit(old_layout_message(known))
        # Another computer may have downloaded more songs into it (a synced folder): its record says.
        archives.adopt(known)
        numbering.tidy(known, wav=wav or archives.read_meta(archive_id).get("wav", False))
    # What the playlist has now, against what's here: all the questions before downloading.
    found, choices = None, {}
    try:
        found = review.check(url, known, output, extra)
    except review.Unavailable as e:
        print(f"Couldn't go over the playlist first ({e}): downloading what's new, without moving anything.")
    # The library leaves the folder alone meanwhile (it would number songs brought in as if added
    # by hand, under this download's feet).
    with layout.working(known or (found["folder"] if found else None)):
        if found:
            choices = review.ask(found["conflicts"], review.decisions(decide))
            if found["removed"] and archive_id != archives.SINGLES:
                for old, new in review.to_singles(found["removed"], archive_id):
                    print(f"  {old.name}: not in the playlist anymore, moved to Singles ({new})")
                review.close_gaps(known)
            for vid, choice in choices.items():
                if choice == review.DOWNLOAD:
                    review.edit_archive(archive_id, drop=[vid])
                else:  # copied or moved after the download: not downloaded again
                    review.edit_archive(archive_id, add=[vid])
        # New songs go after the last one in the folder (songs added by hand, numbered first, or
        # an order of its own), not by their place in the playlist.
        last = numbering.highest(known) if known else None
        # yt-dlp writes the playlist's name here once it's done, for "song-wizard archives".
        title_file = Path(tempfile.mkstemp(prefix="song-wizard-", suffix=".txt")[1])
        # And the path of each song once it's in place, to remember the playlist's folder.
        files_file = Path(tempfile.mkstemp(prefix="song-wizard-", suffix=".txt")[1])
        args = [
            sys.executable, "-m", "yt_dlp",
            "-f", "bestaudio[acodec=opus]/bestaudio",
            "-x",
            "--windows-filenames",
            "--embed-metadata",
            "--download-archive", str(archive),
            "--print-to-file", "playlist:%(title)s", str(title_file),
            "--print-to-file", "after_move:%(id)s\t%(filepath)s", str(files_file),
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
            got = [l.split("\t", 1) if "\t" in l else [None, l]
                   for l in files_file.read_text(errors="replace").splitlines() if l.strip()]
            files = [path for _, path in got]
            title_file.unlink(missing_ok=True)
            files_file.unlink(missing_ok=True)
        folder = known or (str(Path(files[-1]).parent) if files else None)
        # What was decided to be copied or moved comes in now, as if it had just been downloaded.
        brought = []
        if found and choices:
            target = Path(folder) if folder else found["folder"]
            brought = review.bring(found["conflicts"], choices, target, archive_id)
            folder = folder or (str(target) if target.is_dir() else None)
        # Named by its data, "001 - Artist - Title", as the song's data window names it: what the
        # site put there (often the uploader as the artist) shows up front, to be corrected by hand.
        # Numbered as downloads always were: in a playlist downloaded before, after its last song, in
        # the playlist's order; in a new one, by the place each has in the playlist.
        order = {vid: i for i, vid in enumerate(found["order"])} if found else {}
        arrivals = [(vid, Path(path), None) for vid, path in got if Path(path).is_file()]
        arrivals += [(vid, main, (choice, old)) for choice, old, vid, main in brought]
        arrivals.sort(key=lambda a: order.get(a[0], len(order)))
        singles = folder and review.is_singles(folder)
        n = 0
        for vid, path, how in arrivals:
            try:
                if singles:
                    final = numbering.name(path)
                elif last is not None and Path(known).resolve() in (path.parent.resolve(), path.parent.parent.resolve()):
                    # Downloaded (loose in the folder) or brought in (in its own folder already).
                    n += 1
                    final = numbering.name(path, last[0] + n, last[1])
                elif how and vid in order:
                    final = numbering.name(path, order[vid] + 1, 3)  # its place in the new playlist
                else:
                    final = numbering.name(path)
            except SystemExit as e:  # one song that couldn't be named doesn't stop the rest
                print(f"  {path.name}: left as it was ({e.code})")
                code = code or 1
                continue
            if how:
                print(f"  {how[1].name}: {'copied' if how[0] == review.COPY else 'moved'} to the playlist as {final.parent.name}")
        if archive.exists():
            archives.remember(archive_id, url, lines[-1] if lines else None, folder=folder, wav=wav)
    return code
