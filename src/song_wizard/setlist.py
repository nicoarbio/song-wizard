"""A printable setlist of a folder: number, song, key, tempo and length, with the total. In the
order of the files ("001 - ..."). Written as Setlist.html (one A4 page, big enough to read from
the floor) and Setlist.txt in the folder; the interface shows the same page."""

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


def rows(folder, here):
    from .ui import duration

    out = []
    for n, song in enumerate(folder["songs"], 1):
        title, artist = title_of(song["name"])
        key = (song["key"] or "").split()
        tempo = re.match(r"([\d.]+) BPM", song["bpm"] or "")
        out.append({"n": n, "title": title, "artist": artist,
                    "key": (key[0] + ("?" if "uncertain" in song["key"] else "")) if key else "",
                    "bpm": f"{float(tempo[1]):.0f}" if tempo else "",
                    "seconds": duration(here / song["name"])})
    return out


def text(name, items):
    total = sum(r["seconds"] or 0 for r in items)
    width = max([len(r["title"]) for r in items] + [4])
    lines = [name, ""]
    for r in items:
        lines.append(f"{r['n']:>3}. {r['title']:<{width}}  {r['key']:<4} {r['bpm']:>3}  {clock(r['seconds']):>5}"
                     + (f"  ({r['artist']})" if r["artist"] else ""))
    lines += ["", f"{len(items)} songs, {clock(total)}"]
    return "\n".join(lines) + "\n"


def page(name, items):
    """The printable page. Everything shown is escaped: names come from downloaded titles."""
    total = sum(r["seconds"] or 0 for r in items)
    # Big enough to read from the floor, small enough to fit the whole set on one A4 page.
    size = max(9, min(20, int(410 / max(len(items), 1))))
    body = "\n".join(
        f"<tr><td class=n>{r['n']}</td><td class=t><b>{html.escape(r['title'])}</b>"
        + (f" <span class=a>{html.escape(r['artist'])}</span>" if r["artist"] else "")
        + f"</td><td class=k>{html.escape(r['key'])}</td><td class=b>{r['bpm']}</td><td class=d>{clock(r['seconds'])}</td></tr>"
        for r in items)
    return f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
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
  .print {{ margin: 16px 0; padding: 8px 16px; font-size: 12pt; cursor: pointer; }}
  @media print {{ body {{ margin: 0; max-width: none; padding: 0; }} .print {{ display: none; }} }}
</style></head>
<body>
<h1>{html.escape(name)}</h1>
<div class="meta">{len(items)} temas · {clock(total)}</div>
<table><thead><tr><th class=n>#</th><th>Tema</th><th class=k>Tono</th><th class=b>BPM</th><th class=d>Dura</th></tr></thead>
<tbody>
{body}
</tbody></table>
<button class="print" onclick="print()">Imprimir</button>
</body></html>
"""


def run(path, name=None):
    folder, here = find(path)
    if folder is None:
        die(f"{path}: not a folder of the library (see song-wizard list).")
    if not folder["songs"]:
        die(f"{system.shown_path(here)} has no songs.")
    items = rows(folder, here)
    name = name or (folder["playlist"]["title"] if folder["playlist"] else here.name)
    print(text(name, items), end="")
    (here / "Setlist.txt").write_text(text(name, items), encoding="utf-8")
    (here / "Setlist.html").write_text(page(name, items), encoding="utf-8")
    print(f"\nSaved Setlist.txt and Setlist.html (to print: open it in the browser) in {system.shown_path(here)}")
