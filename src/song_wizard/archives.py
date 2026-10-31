"""The per-playlist download archives: what has been downloaded so far."""

import datetime
import json
import subprocess
import sys

from .paths import ARCHIVE_DIR

SINGLES = "singles"


def remember(archive_id, url, title):
    """Store the playlist's URL and name next to its archive (the archive only has video IDs)."""
    meta_path = ARCHIVE_DIR / f"{archive_id}.json"
    meta = read_meta(archive_id)
    meta["url"] = url if archive_id != SINGLES else None
    if title:
        meta["title"] = title
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2))


def read_meta(archive_id):
    try:
        return json.loads((ARCHIVE_DIR / f"{archive_id}.json").read_text())
    except (OSError, ValueError):
        return {}


def fetch_title(archive_id):
    """Archives made before names were stored: ask YouTube once and keep the answer."""
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
            title = "Singles (single videos)"
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
