"""The per-playlist download archives: what has been downloaded so far."""

import datetime
import json
import shutil
import subprocess
import sys
from pathlib import Path

from .paths import ARCHIVE_DIR

SINGLES = "singles"


def remember(archive_id, url, title, folder=None, wav=None):
    """Store the playlist's URL, name and folder next to its archive (the archive only has video
    IDs), and whether it was downloaded with --wav, to look for new songs the same way."""
    meta_path = ARCHIVE_DIR / f"{archive_id}.json"
    meta = read_meta(archive_id)
    meta["url"] = url if archive_id != SINGLES else None
    if title:
        meta["title"] = title
    if folder:
        meta["folder"] = folder
        add_place(Path(folder).parent)
    if wav is not None:
        meta["wav"] = wav
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2))


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
    if folder not in known:
        ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
        places_file().write_text("".join(f"{p}\n" for p in [*known, folder]))


def places():
    """Every folder downloads went into: the ones remembered, plus the parents of the folders the
    archives recorded (for archives from before places were kept). Only those that exist."""
    found = places_file().read_text().splitlines() if places_file().exists() else []
    for path in sorted(ARCHIVE_DIR.glob("*.json")) if ARCHIVE_DIR.exists() else []:
        folder = read_meta(path.stem).get("folder")
        if folder:
            found.append(str(Path(folder).resolve().parent))
    return [Path(p) for p in dict.fromkeys(found) if p and Path(p).is_dir()]


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
        (ARCHIVE_DIR / f"{archive_id}.txt").unlink(missing_ok=True)
        (ARCHIVE_DIR / f"{archive_id}.json").unlink(missing_ok=True)
    print(f"Deleted {len(chosen)} archive{'s' if len(chosen) != 1 else ''}.")
