"""A song's lyrics, with the band's highlights and notes on them. Fetched from an open lyrics
database (or pasted), and saved next to the song as "<song>.lyrics.json", which renaming and
deleting the song take along.

The file: {"text": the lyrics, "synced": [[seconds, line], ...] or null (when the database has them
timed), "marks": [{"line", "from", "to", "color"}] (highlighted characters of a line),
"notes": {line number: note}, "times": {line number: seconds} (when each line starts, set by hand
in the practice player; taken from "synced" until then), "legend": {color: what it means},
"source": where it came from}."""

import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from . import __version__
from .audio import base_of, die, expand

API = "https://lrclib.net/api"
COLORS = ("yellow", "green", "blue", "pink", "orange")
SUFFIX = ".lyrics.json"
LRC_LINE = re.compile(r"^\[(\d+):(\d+(?:\.\d+)?)\]\s?(.*)$")


def path_for(song):
    song = Path(song)
    return song.parent / f"{base_of(song.name)}{SUFFIX}"


def load(song):
    try:
        return json.loads(path_for(song).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def clean(data):
    """What the page sent, checked and trimmed to the expected shape; ValueError if it's wrong."""
    if not isinstance(data, dict) or not isinstance(data.get("text"), str) or len(data["text"]) > 100_000:
        raise ValueError("text")
    lines = data["text"].split("\n")
    marks = []
    for m in data.get("marks") or []:
        line, start, end, color = int(m["line"]), int(m["from"]), int(m["to"]), str(m["color"])
        if color not in COLORS or not 0 <= line < len(lines) or not 0 <= start < end <= len(lines[line]):
            raise ValueError("mark")
        marks.append({"line": line, "from": start, "to": end, "color": color})
    notes = {}
    for k, v in (data.get("notes") or {}).items():
        if not 0 <= int(k) < len(lines) or not isinstance(v, str) or len(v) > 2000:
            raise ValueError("note")
        if v.strip():
            notes[str(int(k))] = v.strip()
    times = {}
    for k, v in (data.get("times") or {}).items():
        if not 0 <= int(k) < len(lines) or not 0 <= float(v) < 36000:
            raise ValueError("time")
        times[str(int(k))] = round(float(v), 2)
    legend = {c: str(v)[:60] for c, v in (data.get("legend") or {}).items() if c in COLORS and str(v).strip()}
    synced = data.get("synced")
    if synced is not None:
        synced = [[float(t), str(line)] for t, line in synced]
    return {"text": data["text"], "synced": synced, "marks": marks, "notes": notes, "times": times, "legend": legend,
            "source": str(data.get("source") or "")[:200]}


def save(song, data):
    data = clean(data)
    path = path_for(song)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, path)
    return data


def parse_lrc(text):
    """Timed lyrics ("[01:02.50] line") -> [[seconds, line], ...]."""
    out = []
    for raw in (text or "").splitlines():
        match = LRC_LINE.match(raw.strip())
        if match:
            out.append([round(int(match[1]) * 60 + float(match[2]), 2), match[3]])
    return out or None


def get(url, tries=2):
    """JSON from the database; a busy moment (5xx, timeout) is tried once more."""
    request = urllib.request.Request(url, headers={"User-Agent": f"song-wizard/{__version__} (https://github.com/nicoarbio/song-wizard)"})
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return json.loads(response.read())
    except (urllib.error.URLError, TimeoutError) as e:
        busy = not isinstance(e, urllib.error.HTTPError) or e.code >= 500
        if tries <= 1 or not busy:
            raise
        time.sleep(2)
        return get(url, tries - 1)


def search(title, artist="", seconds=None):
    """The best match in the database: plain text (and timed lines if any), or None.

    The closest in length wins (the same song comes in several albums and edits); one more than
    15 s off is probably another version, and only taken if there's nothing better."""
    queries = [{"track_name": title, "artist_name": artist} if artist else {"q": title}]
    if " - " in title:
        # A video uploaded by someone else: its "artist" is whoever uploaded it, and the title
        # holds the real one ("Band - Song").
        real_artist, real_title = (part.strip() for part in title.split(" - ", 1))
        queries.append({"track_name": real_title, "artist_name": real_artist})
    if artist:  # "Artist - Title" may have been the other way around
        queries.append({"q": f"{artist} {title}"})
    found = []
    for query in queries:
        found = [r for r in get(f"{API}/search?{urllib.parse.urlencode(query)}") if r.get("plainLyrics") or r.get("syncedLyrics")]
        if found:
            break
    if not found:
        return None
    if seconds:
        found.sort(key=lambda r: (abs((r.get("duration") or 0) - seconds) > 15, abs((r.get("duration") or 0) - seconds),
                                  not r.get("syncedLyrics")))
    best = found[0]
    synced = parse_lrc(best.get("syncedLyrics"))
    text = best.get("plainLyrics") or "\n".join(line for _, line in synced or [])
    return {"text": text.strip("\n"), "synced": synced, "marks": [], "notes": {}, "legend": {},
            "source": f"{best.get('artistName', '')} - {best.get('trackName', '')} ({round(best.get('duration') or 0)} s), "
                      f"lrclib #{best.get('id')}"}


class Unavailable(OSError):
    """The lyrics database was reached but couldn't answer (down or busy: 503 and the like)."""


def fetch(song):
    """Look up the lyrics of a song file by its name and length. None if not found; Unavailable if
    the database is down or busy; OSError if it can't be reached at all."""
    from .tags import title_artist
    from .ui import duration

    title, artist = title_artist(song)
    try:
        return search(title, artist, duration(Path(song)))
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise Unavailable(f"the lyrics database answered {e.code}: it's down or busy, try again in a while") from e
    except (urllib.error.URLError, TimeoutError, ValueError) as e:
        raise OSError(f"couldn't reach the lyrics database ({getattr(e, 'reason', e)})") from e


def run(paths, text_from=None, force=False, export_page=False, kind="lyrics", shift=0, simple=False, bars=4):
    songs = list(expand(paths, skip_generated=True))
    if not songs:
        die("No songs given.")
    if export_page:
        for song in songs:
            print(f"  saved  {export(song, kind, shift, simple, bars)}  (open it in the browser to print it)")
        return
    if text_from is not None:
        text = sys.stdin.read() if text_from == "-" else Path(text_from).read_text(encoding="utf-8")
        for song in songs:
            old = load(song) or {}
            keep = old.get("text") == text  # same text: keep the marks, notes and times
            save(song, {"text": text, "synced": None, "marks": old.get("marks", []) if keep else [],
                        "times": old.get("times", {}) if keep else {},
                        "notes": old.get("notes", {}) if keep else {}, "legend": old.get("legend", {}), "source": "pasted"})
            print(f"  saved  {path_for(song).name}")
        return
    failed = []
    for song in songs:
        name = os.path.basename(song)
        existing = load(song)
        if existing and not force:
            print(f"  has lyrics  {name}  (--force looks them up again; marks and notes are lost)")
            if len(songs) == 1:
                print("\n" + existing["text"])
            continue
        try:
            found = fetch(song)
        except OSError as e:
            print(f"  failed      {name}  ({e})")
            failed.append(name)
            continue
        if not found:
            print(f"  not found   {name}  (paste them with --from FILE, or in the interface)")
            continue
        if existing:
            found["legend"] = existing.get("legend", {})
        save(song, found)
        print(f"  found       {name}  ({found['source']}{', timed' if found['synced'] else ''})")
        if len(songs) == 1:
            print("\n" + found["text"])
    if failed:
        die(f"{len(failed)} could not be looked up; try again in a while.")


# Highlight colors, light enough to read black text on, on screen and on paper.
SHADES = {"yellow": "#ffe066", "green": "#b2f2bb", "blue": "#a5d8ff", "pink": "#fcc2d7", "orange": "#ffc078"}
# Each color's name, by its text key (see i18n).
NAMES = {"yellow": "lyrics.yellow", "green": "lyrics.green", "blue": "lyrics.light_blue", "pink": "lyrics.pink", "orange": "lyrics.orange"}


def runs(line, marks):
    """A line cut where its color changes: [(text, color or None)]."""
    colors = [None] * len(line)
    for m in marks:
        for i in range(m["from"], min(m["to"], len(line))):
            colors[i] = m["color"]
    out = []
    for ch, color in zip(line, colors):
        if out and out[-1][1] == color:
            out[-1][0] += ch
        else:
            out.append([ch, color])
    return [tuple(r) for r in out]


# The look of the lyrics on paper, shared with the setlist (which can add them after the list).
STYLE = """
  .legend { display: flex; flex-wrap: wrap; gap: 4px 16px; font-size: 10pt; color: #333; margin-bottom: 12px; }
  .lyrics { font-size: 13pt; line-height: 1.5; }
  .l { break-inside: avoid; }
  mark { color: inherit; padding: 0 1px; border-radius: 2px; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
  .note { margin-left: 12px; font-size: 10pt; font-style: italic; color: #b03; }
  .note::before { content: "← "; }
  @media print { .lyrics.long { columns: 2; column-gap: 10mm; font-size: 11.5pt; } }
"""


def section(data):
    """The legend and the lyrics with their highlights and notes, as HTML (everything escaped)."""
    from html import escape

    lines = data["text"].split("\n")
    by_line = {}
    for m in data.get("marks", []):
        by_line.setdefault(m["line"], []).append(m)
    body = []
    for i, line in enumerate(lines):
        spans = "".join(f'<mark style="background:{SHADES[c]}">{escape(t)}</mark>' if c else escape(t)
                        for t, c in runs(line, by_line.get(i, [])))
        note = data.get("notes", {}).get(str(i))
        body.append(f'<div class="l">{spans or "&nbsp;"}'
                    + (f'<span class="note">{escape(note)}</span>' if note else "") + "</div>")
    legend = "".join(f'<span><mark style="background:{SHADES[c]}">&nbsp;&nbsp;&nbsp;</mark> {escape(v)}</span>'
                     for c, v in data.get("legend", {}).items() if c in SHADES)
    return (f'<div class="legend">{legend}</div>\n'
            f'<div class="lyrics{" long" if len(lines) > 40 else ""}">\n' + "\n".join(body) + "\n</div>")


def export(song, kind="lyrics", shift=0, simple=False, bars=4):
    """Write the printable page next to the song (with the chords or the bass's notes over the
    lyrics, if asked); returns its path."""
    from . import sheet
    from .tags import title_artist

    data = load(song)
    have = sheet.available(song, data)
    if kind == "lyrics" and not data:
        die(f"{os.path.basename(song)} has no lyrics yet: song-wizard lyrics finds them.")
    if kind == "chords" and kind not in have:
        die(f"{os.path.basename(song)} has no chords yet: song-wizard chords finds them.")
    if kind == "bass" and kind not in have:
        die(f"{os.path.basename(song)} has no bass notes yet: song-wizard notes --part bass finds them.")
    title, artist = title_artist(song)
    name = {"lyrics": "lyrics", "chords": "chords", "bass": "bass"}[kind]
    out = Path(song).parent / f"{base_of(Path(song).name)}.{name}.html"
    out.write_text(sheet.page(f"{title} ({artist})" if artist else title, song, data, kind=kind, shift=shift,
                              simple=simple, bars=bars), encoding="utf-8")
    return out
