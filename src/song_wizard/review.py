"""Before downloading a playlist: what it has now, against the songs already here.

The playlist is asked for as a list (yt-dlp, nothing downloaded) and compared, video by video,
with the link each song downloaded keeps ("purl" in its data; songs added by hand have none and
are never touched):

- A song of this playlist's folder that isn't in the playlist anymore goes to Singles, with its
  folder, on its own; the songs after it move up a number, so there are no gaps. Only when the
  whole list came back: an empty list or an error moves nothing.
- A song of the playlist that's already here, but somewhere else, is asked about first, all of
  them before anything is downloaded: download it again, copy the one here (with its stems, data
  and REAPER project) or, from Singles only, move it to the playlist. One in another playlist
  isn't moved: it belongs there too. What's copied or moved goes at the end, with the new ones.
"""

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from . import archives, song
from .paths import music_dir

DOWNLOAD, COPY, MOVE = "download", "copy", "move"
CHOICES = (DOWNLOAD, COPY, MOVE)
VIDEO = re.compile(r"(?:[?&]v=|youtu\.be/|/shorts/)([A-Za-z0-9_-]{11})")


class Unavailable(Exception):
    """The playlist couldn't be listed (no internet, a private playlist...)."""


def video_of(link):
    """The video id in a song's link ("https://www.youtube.com/watch?v=ID"), or None."""
    match = VIDEO.search(link or "")
    return match[1] if match else None


def listing(url, output, extra=()):
    """[(id, title, where yt-dlp would put it)] of a link, in the playlist's order, and whether
    that's all of it (the count the site gives matches)."""
    from .download import node_ok

    args = [sys.executable, "-m", "yt_dlp", "--flat-playlist", "--no-warnings", "--windows-filenames",
            "-o", output, "--print", "%(id)s\t%(playlist_count|)s\t%(title)s", "--print", "filename"]
    if node_ok():
        args += ["--js-runtimes", "node"]
    done = subprocess.run([*args, *extra, url], capture_output=True, text=True)
    lines = done.stdout.splitlines()
    if done.returncode != 0 or not lines:
        raise Unavailable((done.stderr.strip().splitlines() or ["no answer"])[-1])
    found, count = [], None
    for info, where in zip(lines[0::2], lines[1::2]):
        vid, total, title = (info.split("\t", 2) + ["", ""])[:3]
        found.append((vid, title, where))
        count = int(total) if total.isdigit() else count
    complete = bool(found) and (count is None or count == len(found))
    return found, complete


def containers():
    """Every folder of songs in the library (the music folder, its folders, the places downloads
    went and theirs, and the playlists' folders)."""
    from .ui import subfolders_of

    places = [music_dir(), *archives.places()]
    found = [f for p in places for f in [p, *subfolders_of(p)]]
    found += [Path(p["folder"]) for p in archives.playlists() if p.get("folder")]
    seen = {}
    for f in found:
        try:
            if f.is_dir() and not song.is_song(f):
                seen.setdefault(f.resolve(), f)
        except OSError:
            pass
    return list(seen.values())


def singles_folder():
    """Where single songs go: the folder the last single was downloaded to, else Music/Singles."""
    folder = archives.read_meta(archives.SINGLES).get("folder")
    return Path(folder) if folder and Path(folder).is_dir() else music_dir() / "Singles"


def is_singles(container):
    record = archives.read_record(container)
    if record:
        return record["id"] == archives.SINGLES
    return Path(container).resolve() == singles_folder().resolve() or Path(container).name == "Singles"


def index():
    """{video id: (song's folder, its folder of songs)} of every downloaded song in the library."""
    from . import tags

    found = {}
    for container in containers():
        songs = song.songs_in(container)
        data = tags.read_many(song.main_in(s) for s in songs)
        for s in songs:
            vid = video_of(data[song.main_in(s)].get("purl"))
            if vid:
                found.setdefault(vid, (s, container))
    return found


def check(url, folder, output, extra=()):
    """What downloading this link will meet: {"title", "folder" (where its songs go), "complete",
    "removed": [song folders leaving for Singles], "conflicts": [{"id", "title", "song" (its folder),
    "where" ("singles" or the playlist's name), "choices"}]}."""
    remote, complete = listing(url, output, extra)
    target = Path(folder) if folder else Path(os.path.dirname(remote[0][2]))
    here = index()
    ids = [vid for vid, _, _ in remote]
    removed = []
    if complete and target.is_dir() and not is_singles(target):
        for vid, (s, container) in here.items():
            if container.resolve() == target.resolve() and vid not in ids:
                removed.append(s)
    conflicts = []
    for vid, title, _ in remote:
        if vid not in here:
            continue
        s, container = here[vid]
        if target.exists() and container.resolve() == target.resolve():
            continue  # already in this playlist
        singles = is_singles(container)
        if singles and is_singles(target):
            continue  # a single link to a song already in Singles
        name = (archives.read_record(container) or {}).get("title") or container.name
        conflicts.append({"id": vid, "title": title, "song": s, "where": "singles" if singles else name,
                          "choices": [DOWNLOAD, COPY, MOVE] if singles else [DOWNLOAD, COPY]})
    return {"title": None, "folder": target, "complete": complete,
            "removed": sorted(removed, key=lambda p: p.name.lower()), "conflicts": conflicts}


def ask(conflicts, decided):
    """{id: choice} for every conflict: the ones given, else asked in the terminal. Without a
    terminal, exits listing them (nothing has been downloaded or moved)."""
    choices = {}
    missing = [c for c in conflicts if decided.get(c["id"]) not in c["choices"]]
    if missing and not sys.stdin.isatty():
        lines = [f"  {c['song'].name}  (in {where(c)}; --decide {c['id']}={'|'.join(c['choices'])})" for c in missing]
        sys.exit("Nothing downloaded: these songs of the playlist are already here, and there's no terminal "
                 "to ask what to do with them:\n" + "\n".join(lines))
    for c in conflicts:
        if c in missing:
            keys = {"d": DOWNLOAD, "c": COPY, "m": MOVE}
            options = ", ".join(f"[{k}] {v}" for k, v in keys.items() if v in c["choices"])
            prompt = f"{c['song'].name} is already in {where(c)}: {options}? "
            while (answer := keys.get(input(prompt).strip().lower()[:1])) not in c["choices"]:
                pass
            choices[c["id"]] = answer
        else:
            choices[c["id"]] = decided[c["id"]]
    return choices


def where(conflict):
    return "Singles" if conflict["where"] == "singles" else f'the playlist "{conflict["where"]}"'


def archive_lines(vid):
    return f"youtube {vid}"


def edit_archive(archive_id, add=(), drop=()):
    """Add or take out songs ("youtube <id>") of a playlist's archive, and keep its folder's record."""
    path = archives.ARCHIVE_DIR / f"{archive_id}.txt"
    lines = archives.downloaded(archive_id)
    gone = {archive_lines(v) for v in drop}
    new = [l for l in lines if l not in gone] + [archive_lines(v) for v in add if archive_lines(v) not in lines]
    if new != lines:
        archives.ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
        path.write_text("".join(f"{l}\n" for l in new))
        archives.write_record(archive_id)


def plain_name(name):
    from .rename import NUMBER
    return name[NUMBER.match(name).end():] if NUMBER.match(name) else name


def free(path):
    """path, or "path (2)"... if it's taken."""
    n, candidate = 1, path
    while candidate.exists():
        n += 1
        candidate = path.with_name(f"{path.name} ({n})")
    return candidate


def to_singles(songs, archive_id):
    """Songs that left the playlist: to Singles with their folders, without a number, out of the
    playlist's archive and into Singles'. Returns [(song, its new folder)]."""
    if not songs:
        return []
    from .tags import read
    dest = singles_folder()
    dest.mkdir(parents=True, exist_ok=True)
    moved = []
    for s in songs:
        vid = video_of(read(song.main_in(s)).get("purl"))
        target = free(dest / plain_name(s.name))
        shutil.move(str(s), str(target))
        rebase(target, s.name)
        edit_archive(archive_id, drop=[vid])
        edit_archive(archives.SINGLES, add=[vid])
        moved.append((s, target))
    archives.remember(archives.SINGLES, None, None, folder=str(dest))
    return moved


def rebase(target, old):
    """A song's folder copied or moved under a new name: its own files (the song in each format,
    its REAPER project and peaks, its printed pages) take the new name too."""
    from . import reaper, rename

    if target.name == old:
        return
    for sub in [target, target / "peaks"]:
        if sub.is_dir():
            for name, rest in rename.group(sub, old):
                os.rename(sub / name, sub / (target.name + rest))
    for project in [*target.glob("*.rpp"), *target.glob("*.rpp-bak")]:
        reaper.rename_inside(project, old, target.name)


def close_gaps(folder):
    """Number the folder's songs 1, 2, 3... in the order they have (no gaps after one left)."""
    from . import numbering
    from .rename import NUMBER

    found = numbering.songs(folder)
    numbered = sorted((b for b in found if NUMBER.match(b)), key=lambda b: (numbering.number_of(b), b.lower()))
    expected = [f"{i:0{max(3, len(str(len(numbered))))}d}" for i in range(1, len(numbered) + 1)]
    if [NUMBER.match(b).group(0)[:-3] for b in numbered] != expected:
        import contextlib
        import io
        with contextlib.redirect_stdout(io.StringIO()):
            numbering.reorder(folder, numbered)


def bring(conflicts, choices, folder, archive_id):
    """Copy or move the songs decided so into the playlist's folder, after its last song.
    Returns [(choice, song, its new main file)]."""
    from . import numbering

    done = []
    picked = [c for c in conflicts if choices[c["id"]] in (COPY, MOVE)]
    if not picked:
        return done
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    for c in picked:
        last, digits = numbering.highest(folder)
        target = free(folder / plain_name(c["song"].name))
        if choices[c["id"]] == MOVE:
            shutil.move(str(c["song"]), str(target))
            edit_archive(archives.SINGLES, drop=[c["id"]])
        else:
            shutil.copytree(c["song"], target)
        rebase(target, c["song"].name)
        # Singles has no numbers; a playlist, the one after its last song.
        main = numbering.name(song.main_in(target)) if is_singles(folder) else \
            numbering.name(song.main_in(target), last + 1, digits)
        edit_archive(archive_id, add=[c["id"]])
        done.append((choices[c["id"]], c["song"], main))
    return done


def decisions(items):
    """--decide ID=choice, as given in the terminal or by the interface -> {id: choice}."""
    found = {}
    for item in items or []:
        vid, _, choice = str(item).partition("=")
        if choice not in CHOICES:
            sys.exit(f'"{item}": write it as VIDEO_ID=download, VIDEO_ID=copy or VIDEO_ID=move.')
        found[vid.strip()] = choice
    return found


def summary(found):
    """What check() found, for the interface (paths as strings)."""
    return {"folder": str(found["folder"]), "complete": found["complete"],
            "removed": [s.name for s in found["removed"]],
            "conflicts": [{**c, "song": c["song"].name} for c in found["conflicts"]]}


def dumps(found):
    return json.dumps(summary(found), ensure_ascii=False)
