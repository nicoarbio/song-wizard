"""The per-playlist download archives: what has been downloaded so far."""

import datetime
import json
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
    width = max(len(r[1]) for r in rows)
    print(f"  {'#':>2}  {'Playlist':<{width}}  {'Songs':>5}  Last download")
    for i, (_, title, songs, changed) in enumerate(rows, 1):
        print(f"  {i:>2}  {title:<{width}}  {songs:>5}  {changed:%Y-%m-%d %H:%M}")
    print(f"\nArchives are in {ARCHIVE_DIR}")


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
