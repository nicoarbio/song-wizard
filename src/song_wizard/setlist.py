"""A printable setlist: number, song, key, tempo and length, with the total. Of a folder, in the
order of its files ("001 - ..."), written as Setlist.html (one A4 page, big enough to read from
the floor) and Setlist.txt in the folder; or of songs from any folders, in the order given, which
touches no folder. The lyrics, with their marks, can follow on the next pages. The interface shows
the same page."""

import html
import os
import re
from pathlib import Path

from . import system
from .audio import die
from .paths import music_dir

# Bits of downloaded titles that say nothing on a setlist: "(Official Video)", "[HD]"...
NOISE = re.compile(r"\s*[(\[][^()\[\]]*\b(official|audio|video|lyrics?|hd|hq|4k|remaster(ed)?|visualizer|videoclip)\b"
                   r"[^()\[\]]*[)\]]", re.IGNORECASE)


def title_of(name):
    """"003 - Artist - Song (Official Video).opus" -> ("Song", "Artist")."""
    stem = re.sub(r"^\d+\s*-\s*", "", os.path.splitext(name)[0])
    stem = NOISE.sub("", stem).strip()
    artist, sep, title = stem.partition(" - ")
    return (title.strip(), artist.strip()) if sep and title.strip() else (stem, "")


def clock(seconds):
    if seconds is None:
        return ""
    seconds = round(seconds)
    return f"{seconds // 3600}:{seconds // 60 % 60:02d}:{seconds % 60:02d}" if seconds >= 3600 else f"{seconds // 60}:{seconds % 60:02d}"


def find(path, root=None):
    """The library folder at this path, and the folder on disk."""
    from .listing import folder_path
    from .ui import library

    root = root or music_dir()
    target = Path(system.local_path(str(path))).resolve()
    for folder in library(root):
        here = folder_path(root, folder)
        if here.resolve() == target:
            return folder, here
    return None, target


def row(n, song, here):
    from .tags import title_artist
    from .ui import duration

    # From the song's data ("title", "artist"), else from its file name.
    title, artist = title_artist(here / song["name"], song.get("tags"))
    key = (song["key"] or "").split()
    tempo = re.match(r"([\d.]+) BPM", song["bpm"] or "")
    return {"n": n, "title": title, "artist": artist, "path": here / song["name"],
            "key": (key[0] + ("?" if "uncertain" in song["key"] else "")) if key else "",
            "bpm": f"{float(tempo[1]):.0f}" if tempo else "",
            "seconds": duration(here / song["name"])}


def rows(folder, here):
    return [row(n, song, here) for n, song in enumerate(folder["songs"], 1)]


def pick(paths, root=None):
    """The songs at these paths, in this order, from any folders of the library: (song, folder on
    disk). A stem or a version stands for its song. Raises LookupError with the first path that
    isn't a song of the library."""
    from .listing import folder_path
    from .ui import library

    root = root or music_dir()
    known = {}
    for folder in library(root):
        if folder.get("missing"):
            continue
        here = folder_path(root, folder)
        for song in folder["songs"]:
            for name in [song["name"], *(f["name"] for f in song["files"])]:
                known.setdefault(str((here / name).resolve()), (song, here))
    out = []
    for path in paths:
        found = known.get(str(Path(system.local_path(str(path))).resolve()))
        if not found:
            raise LookupError(str(path))
        out.append(found)
    return out


def chosen(paths, root=None):
    return [row(n, song, here) for n, (song, here) in enumerate(pick(paths, root), 1)]


def text(name, items):
    total = sum(r["seconds"] or 0 for r in items)
    width = max([len(r["title"]) for r in items] + [4])
    lines = [name, ""]
    for r in items:
        lines.append(f"{r['n']:>3}. {r['title']:<{width}}  {r['key']:<4} {r['bpm']:>3}  {clock(r['seconds']):>5}"
                     + (f"  ({r['artist']})" if r["artist"] else ""))
    lines += ["", f"{len(items)} songs, {clock(total)}"]
    return "\n".join(lines) + "\n"


def page(name, items, with_lyrics=False, lang="es"):
    """The printable page; with the lyrics of the songs that have them, one song per page after
    the list. Everything shown is escaped: names come from downloaded titles."""
    from . import lyrics
    from .i18n import say

    total = sum(r["seconds"] or 0 for r in items)
    # Big enough to read from the floor, small enough to fit the whole set on one A4 page.
    size = max(9, min(20, int(410 / max(len(items), 1))))
    body = "\n".join(
        f"<tr><td class=n>{r['n']}</td><td class=t><b>{html.escape(r['title'])}</b>"
        + (f" <span class=a>{html.escape(r['artist'])}</span>" if r["artist"] else "")
        + f"</td><td class=k>{html.escape(r['key'])}</td><td class=b>{r['bpm']}</td><td class=d>{clock(r['seconds'])}</td></tr>"
        for r in items)
    sheets = []
    for r in items if with_lyrics else []:
        data = lyrics.load(r["path"])
        if data:
            sheets.append(f'<section class="song"><h2><span class=n>{r["n"]}.</span> {html.escape(r["title"])}'
                          + (f' <span class=a>{html.escape(r["artist"])}</span>' if r["artist"] else "")
                          + f'</h2>\n{lyrics.section(data)}\n</section>')
    return f"""<!doctype html>
<html lang="{lang}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Setlist: {html.escape(name)}</title>
<style>
  @page {{ size: A4; margin: 12mm; }}
  body {{ font-family: system-ui, -apple-system, "Segoe UI", sans-serif; color: #111; background: #fff; margin: 24px auto; max-width: 820px; padding: 0 16px; }}
  h1 {{ font-size: {size + 6}pt; margin: 0 0 4px; }}
  .meta {{ color: #555; font-size: 11pt; margin-bottom: 10px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: {size}pt; }}
  td {{ padding: .12em .35em; border-bottom: 1px solid #ccc; vertical-align: baseline; line-height: 1.25; }}
  th {{ text-align: left; font-size: 10pt; color: #555; font-weight: 600; padding: 0 .35em 4px; border-bottom: 2px solid #111; }}
  .n {{ width: 1.6em; text-align: right; color: #555; }}
  .a {{ color: #666; font-size: .6em; white-space: nowrap; }}
  .k, .b, .d {{ white-space: nowrap; text-align: right; font-variant-numeric: tabular-nums; }}
  .k {{ font-weight: 700; }}
  .song {{ break-before: page; margin-top: 48px; }}
  .song h2 {{ font-size: 20pt; margin: 0 0 6px; }}
  .song h2 .n {{ font-weight: 400; }}
  .print {{ margin: 16px 0; padding: 8px 16px; font-size: 12pt; cursor: pointer; }}
  @media print {{ body {{ margin: 0; max-width: none; padding: 0; }} .print {{ display: none; }} .song {{ margin-top: 0; }} }}
{lyrics.STYLE}</style></head>
<body>
<h1>{html.escape(name)}</h1>
<div class="meta">{html.escape(say(lang, "{n} temas · {total}", n=len(items), total=clock(total)))}</div>
<table><thead><tr><th class=n>#</th><th>{say(lang, "Tema")}</th><th class=k>{say(lang, "Tono")}</th><th class=b>BPM</th><th class=d>{say(lang, "Dura")}</th></tr></thead>
<tbody>
{body}
</tbody></table>
<button class="print" onclick="print()">{say(lang, "Imprimir")}</button>
{chr(10).join(sheets)}
</body></html>
"""


def run(paths=(), name=None, with_lyrics=False, out=None):
    """One folder: its setlist, saved in it (or in out). Songs: theirs, in that order, shown and
    saved only to out."""
    paths = [paths] if isinstance(paths, (str, Path)) else list(paths) or ["."]
    if len(paths) == 1 and Path(system.local_path(str(paths[0]))).is_dir():
        folder, here = find(paths[0])
        if folder is None:
            die(f"{paths[0]}: not a folder of the library (see song-wizard list).")
        if not folder["songs"]:
            die(f"{system.shown_path(here)} has no songs.")
        items = rows(folder, here)
        name = name or (folder["playlist"]["title"] if folder["playlist"] else here.name)
    else:
        try:
            items = chosen(paths)
        except LookupError as e:
            die(f"{e.args[0]}: not a song of the library (see song-wizard list). Give one folder, or songs.")
        name, here = name or "Setlist", None
    print(text(name, items), end="")
    if out:
        out = Path(system.local_path(str(out)))
        out.write_text(page(name, items, with_lyrics), encoding="utf-8")
        print(f"\nSaved {system.shown_path(out)} (to print: open it in the browser)")
    elif here:
        (here / "Setlist.txt").write_text(text(name, items), encoding="utf-8")
        (here / "Setlist.html").write_text(page(name, items, with_lyrics), encoding="utf-8")
        print(f"\nSaved Setlist.txt and Setlist.html (to print: open it in the browser) in {system.shown_path(here)}")
    else:
        print("\nTo print it: --out setlist.html saves it as a page, or use the interface.")
