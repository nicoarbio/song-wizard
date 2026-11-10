"""The per-playlist download archives: what has been downloaded so far."""

import datetime
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

from .paths import ARCHIVE_DIR

SINGLES = "singles"
# Each playlist's folder keeps a copy of its record (what was downloaded into it and from where),
# so the folder carries it: copied to another computer, or kept in a synced drive, the playlist
# shows up there with "look for new songs" working, without downloading again what it has.
RECORD = ".song-wizard.json"


def remember(archive_id, url, title, folder=None, wav=None):
    """Store the playlist's URL, name and folder next to its archive (the archive only has video
    IDs), and whether it was downloaded with --wav, to look for new songs the same way."""
    meta_path = ARCHIVE_DIR / f"{archive_id}.json"
    before = read_meta(archive_id)
    meta = dict(before)
    meta["url"] = url if archive_id != SINGLES else None
    if title:
        meta["title"] = title
    if folder:
        meta["folder"] = folder
        add_place(Path(folder).parent)
    if wav is not None:
        meta["wav"] = wav
    if meta != before or not meta_path.exists():
        ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
        meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2))
    write_record(archive_id)


def downloaded(archive_id):
    """The lines of a playlist's archive: "<site> <id>" of each song downloaded."""
    path = ARCHIVE_DIR / f"{archive_id}.txt"
    return [l for l in path.read_text().splitlines() if l.strip()] if path.exists() else []


def read_record(folder):
    """The record kept in a folder, or None. It may come from anywhere (a shared drive), so only
    a well-formed one counts."""
    try:
        record = json.loads((Path(folder) / RECORD).read_text())
    except (OSError, ValueError):
        return None
    if not isinstance(record, dict) or not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", str(record.get("id", ""))):
        return None
    return record


def write_record(archive_id):
    """Keep a playlist's record in its folder (only when it changed: the folder may be synced)."""
    meta = read_meta(archive_id)
    folder = meta.get("folder")
    if not folder or not Path(folder).is_dir():
        return
    record = {"about": "song-wizard: what was downloaded into this folder, so another computer knows it too",
              "id": archive_id, "title": meta.get("title"), "url": meta.get("url"), "wav": bool(meta.get("wav")),
              "downloaded": downloaded(archive_id)}
    text = json.dumps(record, ensure_ascii=False, indent=2) + "\n"
    path = Path(folder) / RECORD
    try:
        if path.is_file() and path.read_text() == text:
            return
        part = path.with_name(RECORD + ".part")
        part.write_text(text)
        part.replace(path)
    except OSError:
        pass  # a read-only folder: it just doesn't travel with its record


def adopt(folder):
    """Make the playlist recorded in this folder this computer's too, downloading into it from
    now on. The folder's record wins over what this computer had (another one may have
    downloaded more songs into it, or deleted some). Returns its id, or None if the folder has
    no record or this computer downloads that playlist into another folder that's still there."""
    folder = Path(folder).resolve()
    record = read_record(folder)
    if record is None:
        return None
    archive_id = record["id"]
    mine = read_meta(archive_id).get("folder")
    if mine and Path(mine).is_dir() and Path(mine).resolve() != folder:
        return None
    songs = [l for l in record.get("downloaded") or [] if isinstance(l, str) and len(l.split()) == 2]
    archive = ARCHIVE_DIR / f"{archive_id}.txt"
    text = "".join(f"{l}\n" for l in songs)
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    if not archive.exists() or archive.read_text() != text:
        archive.write_text(text)
    url = record.get("url")
    url = url if isinstance(url, str) and re.match(r"https?://", url) else None
    title = record.get("title") if isinstance(record.get("title"), str) else None
    remember(archive_id, url, title, folder=str(folder), wav=bool(record.get("wav")))
    return archive_id


def sync(folders):
    """Take the playlists recorded in these folders, and give the folders of the playlists this
    computer knows their record (those downloaded before records were kept, too)."""
    for folder in folders:
        adopt(folder)
    for path in sorted(ARCHIVE_DIR.glob("*.json")) if ARCHIVE_DIR.exists() else []:
        write_record(path.stem)


def add(folder):
    """Show a folder in the library (a synced drive, a folder copied from another computer) and
    take the playlists recorded in it or in the folders inside it."""
    from . import system

    if letter := system.unmounted_drive(folder):
        sys.exit(system.mount_hint(letter))
    folder = Path(folder).expanduser().resolve()
    if not folder.is_dir():
        sys.exit(f"{folder}: no such folder.")
    inside = sorted((p for p in folder.iterdir() if p.is_dir() and not p.name.startswith(".")),
                    key=lambda p: p.name.lower())
    taken, elsewhere = [], []
    for candidate in [folder, *inside]:
        record = read_record(candidate)
        if record is None:
            continue
        if adopt(candidate):
            taken.append(read_meta(record["id"]).get("title") or candidate.name)
        else:
            elsewhere.append((candidate, read_meta(record["id"]).get("folder")))
    if read_record(folder) is None:
        from .paths import music_dir

        root = music_dir().resolve()
        if folder != root and root not in folder.parents:
            add_place(folder)
    for title in taken:
        print(f"{title}: looking for new songs downloads only what isn't in its folder yet.")
    for candidate, mine in elsewhere:
        print(f"{candidate.name}: this computer already downloads it into {system.shown_path(mine)}; left as it is.")
    if not taken:
        print(f"No playlists recorded in {system.shown_path(folder)}"
              + (" (other than those above)." if elsewhere else
                 "; its songs show in the library. (Playlists downloaded with song-wizard 0.28 or newer carry "
                 "their record: opening the library on the computer that downloaded them writes it.)"))


def forget_sources(links):
    """Take songs out of every archive by the links they were downloaded from (each archive line
    is "<site> <id>", and a downloaded file keeps its link), so downloading the playlist again
    brings them back. Returns how many lines went."""
    gone = 0
    for path in ARCHIVE_DIR.glob("*.txt") if ARCHIVE_DIR.exists() else []:
        lines = path.read_text().splitlines()
        kept = [l for l in lines if not (len(l.split()) == 2 and any(l.split()[1] in link for link in links))]
        if len(kept) != len(lines):
            path.write_text("".join(f"{l}\n" for l in kept))
            gone += len(lines) - len(kept)
            write_record(path.stem)
    return gone


def move(which, dest):
    """Move a playlist's folder, songs and all, into dest (dest/<its name>) and record the new
    place. which: its number in the list or its id. If it was already moved by hand and is found
    in dest, only the new place is recorded."""
    from .paths import music_dir

    rows = [r for r in entries() if r[0] != SINGLES]
    by_number = {str(i): r[0] for i, r in enumerate(entries(), 1) if r[0] != SINGLES}
    archive_id = by_number.get(str(which), which)
    playlist = next((p for p in playlists() if p["id"] == archive_id), None)
    if playlist is None:
        sys.exit(f'No playlist "{which}": use the numbers shown by "song-wizard archives" ({len(rows)} playlists).')
    source = Path(playlist["folder"]) if playlist["folder"] else None
    if source is None or not source.is_dir():
        # Archives from before folders were recorded: look in the music folder by name.
        root = music_dir()
        source = next((f for f in root.iterdir() if f.is_dir() and playlist_for(f, [playlist])), None) if root.is_dir() else None
    from . import system

    if letter := system.unmounted_drive(dest):
        sys.exit(system.mount_hint(letter))
    dest = Path(dest).expanduser().resolve()
    if not dest.is_dir():
        sys.exit(f"{dest}: no such folder.")
    name = source.name if source else (playlist["title"] or archive_id)
    target = dest / name
    if source and source.resolve() == target:
        sys.exit(f"{playlist['title']} is already in {dest}.")
    if source:
        if target.exists():
            sys.exit(f"{target} already exists: nothing moved.")
        print(f"Moving {source} to {target}...", flush=True)
        shutil.move(str(source), str(target))
    elif target.is_dir():
        print(f"Found it in {target}.")
    else:
        sys.exit(f"Can't find the folder of {playlist['title']}; move it by hand and run this again.")
    remember(archive_id, playlist["url"], None, folder=str(target))
    print(f"{playlist['title']} is now in {target}. Looking for new songs downloads them there.")


def places_file():
    return ARCHIVE_DIR / "places.list"


def add_place(folder):
    """Remember a folder downloads went into (a playlist's or Singles' parent), for the library."""
    folder = str(Path(folder).resolve())
    known = places_file().read_text().splitlines() if places_file().exists() else []
    # A folder right inside another place is already shown as one of its folders.
    if folder not in known and str(Path(folder).parent) not in known:
        ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
        places_file().write_text("".join(f"{p}\n" for p in [*known, folder]))


def places(missing=False):
    """Every folder downloads went into: the ones remembered, plus the parents of the folders the
    archives recorded (for archives from before places were kept). Only those that exist, unless
    missing (a drive that isn't connected now, a folder moved by hand)."""
    found = places_file().read_text().splitlines() if places_file().exists() else []
    for path in sorted(ARCHIVE_DIR.glob("*.json")) if ARCHIVE_DIR.exists() else []:
        folder = read_meta(path.stem).get("folder")
        if folder:
            found.append(str(Path(folder).resolve().parent))
    found = [p for p in dict.fromkeys(found) if p]
    # One right inside another place shows already as one of its folders (added with "add
    # folder" before this was checked): not twice.
    found = [p for p in found if str(Path(p).parent) not in found]
    return [Path(p) for p in found if missing or Path(p).is_dir()]


def simple(name):
    """Only letters and digits, lowercase: yt-dlp changes some characters of a playlist's name
    when it makes its folder ("A: B" -> "A： B")."""
    return "".join(c for c in name.lower() if c.isalnum())


def playlists():
    """[{id, title, url, folder, wav}] of the playlists downloaded so far (not single videos)."""
    found = []
    for path in sorted(ARCHIVE_DIR.glob("*.json")) if ARCHIVE_DIR.exists() else []:
        meta = read_meta(path.stem)
        if path.stem != SINGLES and meta.get("url"):
            found.append({"id": path.stem, "title": meta.get("title"), "url": meta["url"],
                          "folder": meta.get("folder"), "wav": bool(meta.get("wav"))})
    return found


def playlist_for(folder, known=None):
    """The playlist downloaded into this folder: the one that recorded it, or, for archives made
    before folders were recorded, the one whose name matches the folder's."""
    known = playlists() if known is None else known
    folder = Path(folder).resolve()
    for p in known:
        if p["folder"] and Path(p["folder"]).resolve() == folder:
            return p
    for p in known:
        if not p["folder"] and p["title"] and simple(p["title"]) == simple(folder.name):
            return p
    return None


def read_meta(archive_id):
    try:
        return json.loads((ARCHIVE_DIR / f"{archive_id}.json").read_text())
    except (OSError, ValueError):
        return {}


def fetch_title(archive_id):
    """Archives made before names were stored: ask the site once and keep the answer."""
    url = f"https://www.youtube.com/playlist?list={archive_id}"
    out = subprocess.run([sys.executable, "-m", "yt_dlp", "--flat-playlist", "-I", "1",
                          "--print", "playlist_title", url], capture_output=True, text=True)
    title = out.stdout.strip().splitlines()[-1] if out.returncode == 0 and out.stdout.strip() else None
    if title:
        meta = read_meta(archive_id)
        meta.setdefault("url", url)
        meta["title"] = title
        (ARCHIVE_DIR / f"{archive_id}.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2))
    return title


def entries():
    """[(archive id, name, number of songs, last change)], sorted by name."""
    rows = []
    for path in ARCHIVE_DIR.glob("*.txt") if ARCHIVE_DIR.exists() else []:
        archive_id = path.stem
        if archive_id == SINGLES:
            title = "Singles (single links)"
        else:
            title = read_meta(archive_id).get("title") or fetch_title(archive_id) or f"(unknown name) {archive_id}"
        songs = sum(1 for line in path.read_text().splitlines() if line.strip())
        changed = datetime.datetime.fromtimestamp(path.stat().st_mtime)
        rows.append((archive_id, title, songs, changed))
    return sorted(rows, key=lambda r: (r[0] == SINGLES, r[1].lower()))


def show(rows=None):
    rows = entries() if rows is None else rows
    if not rows:
        print("Nothing downloaded yet.")
        return
    from . import system

    width = max(len(r[1]) for r in rows)
    print(f"  {'#':>2}  {'Playlist':<{width}}  {'Songs':>5}  {'Last download':<16}  Folder")
    for i, (archive_id, title, songs, changed) in enumerate(rows, 1):
        folder = read_meta(archive_id).get("folder")
        where = system.shown_path(folder) if folder else "(not recorded yet)"
        print(f"  {i:>2}  {title:<{width}}  {songs:>5}  {changed:%Y-%m-%d %H:%M}  {where}")
    print(f"\nArchives are in {ARCHIVE_DIR}")


def update(which):
    """Look for new songs in some playlists (by number or id) or "all": each is downloaded again,
    and its archive makes only the songs added since come down, into its own folder."""
    from .download import fetch

    numbered = {str(i): r[0] for i, r in enumerate(entries(), 1)}
    known = {p["id"]: p for p in playlists()}
    if [w.lower() for w in which] == ["all"]:
        chosen = list(known.values())
    else:
        chosen = []
        for w in which:
            archive_id = numbered.get(str(w), w)
            if archive_id not in known:
                sys.exit(f'No playlist "{w}" to update: use the numbers shown by "song-wizard archives" '
                         "(single songs have no playlist to look in).")
            chosen.append(known[archive_id])
    if not chosen:
        print("No playlists downloaded yet.")
        return
    failed = []
    for p in chosen:
        print(f"Looking for new songs in {p['title'] or p['id']}...", flush=True)
        if fetch(p["url"], wav=p["wav"]) != 0:
            failed.append(p["title"] or p["id"])
    if failed:
        sys.exit("Some playlists had errors: " + ", ".join(failed))


def delete(which, yes=False):
    """Forget playlists, by number in the list or "all". The songs themselves aren't touched."""
    rows = entries()
    if not rows:
        print("Nothing downloaded yet.")
        return
    if [w.lower() for w in which] == ["all"]:
        chosen = rows
    else:
        try:
            numbers = sorted({int(w) for w in which})
        except ValueError:
            sys.exit('Use the numbers shown by "song-wizard archives", or "all".')
        bad = [n for n in numbers if not 1 <= n <= len(rows)]
        if bad:
            sys.exit(f"No archive number {', '.join(map(str, bad))}; there are {len(rows)}.")
        chosen = [rows[n - 1] for n in numbers]

    print("This forgets what was downloaded from:")
    for _, title, songs, _ in chosen:
        print(f"  {title} ({songs} songs)")
    print("Downloading them again will get every song again. The songs already downloaded are kept.")
    if not yes:
        if not sys.stdin.isatty():
            sys.exit("Not deleting without confirmation: add --yes.")
        if input("Delete? [y/N] ").strip().lower() not in ("y", "yes", "s", "si", "sí"):
            print("Nothing deleted.")
            return
    for archive_id, *_ in chosen:
        # The folder's record too, or the library would take the playlist back.
        if (folder := read_meta(archive_id).get("folder")) and read_record(folder):
            try:
                (Path(folder) / RECORD).unlink()
            except OSError:
                pass
        (ARCHIVE_DIR / f"{archive_id}.txt").unlink(missing_ok=True)
        (ARCHIVE_DIR / f"{archive_id}.json").unlink(missing_ok=True)
    print(f"Deleted {len(chosen)} archive{'s' if len(chosen) != 1 else ''}.")
