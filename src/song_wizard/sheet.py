"""The printed lyrics with the chords (or the bass's notes) over the words: a chord sheet.

The chords ("<song>.chords.json") and the bass's notes ("<song>.notes.json") have times; the
lyrics have the time each line starts (set by hand in the practice player, or matched from the
database's timed lines). A chord goes over the word being sung when it changes: its place in the
line is found by spreading the line's letters over the time the line takes. It's approximate
(sheets found online place them by eye too), and it's corrected by moving the chord in Practicar.

Where nobody sings (intro, solos, the end) the chords go in rows of bars on the click's grid:
"| E | C#m | B | B |". Without timed lyrics, the whole song goes that way.

Names follow a pitch shift (-6...+6 semitones, like the practice player) and can be simplified
to major/minor, like the practice player does."""

import base64
import math
import re
from html import escape
from importlib import resources

from . import chords as chords_mod
from . import lyrics as lyrics_mod
from . import notes as notes_mod
from .i18n import say

KINDS = ("lyrics", "chords", "bass")
BARS_PER_ROW = (2, 4)
# A line is sung in about 0.3 s per letter: the letters are spread over that, but at least 2 s
# and at most 8 s, so a line followed by a guitar solo doesn't stretch over the solo.
PER_LETTER, SHORTEST, LONGEST = 0.3, 2.0, 8.0
# A chord changing this little before a line starts goes on its first word (singers lead in).
LEAD = 0.3
SHARPS = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
FLATS = ["C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B"]
CHORD = re.compile(r"^([A-G][#b]?)(maj|min|m|dim|aug|\+|°|ø|sus[24]?|add)?([0-9b#()majdsu+]*)(?:/([A-G][#b]?))?$")


def move_note(note, shift):
    """A note's name, shift semitones away, spelled with flats if it was."""
    names = FLATS if "b" in note else SHARPS
    i = SHARPS.index(note) if note in SHARPS else FLATS.index(note) if note in FLATS else -1
    return note if i < 0 or not shift else names[(i + shift) % 12]


def chord_name(name, shift=0, simple=False):
    """As the practice player shows it (shownChord in ui.html): transposed, and if simple only
    the root and major/minor. A name that isn't read as a chord is kept as written."""
    m = CHORD.match(name)
    if not m:
        return name
    root, quality, extra, bass = m.group(1), m.group(2) or "", m.group(3) or "", m.group(4)
    if simple:
        return move_note(root, shift) + ("m" if quality in ("m", "min", "dim", "°", "ø") else "")
    return move_note(root, shift) + quality + extra + ("/" + move_note(bass, shift) if bass else "")


def plain(text):
    return re.sub(r"[^\w]+|_", "", text.lower())


def line_times(data):
    """{line number: seconds}: set by hand, or, until then, the database's timed lines matched to
    the text's lines in order (as the practice player does)."""
    if data.get("times"):
        return {int(k): float(v) for k, v in data["times"].items()}
    lines, out, j = data["text"].split("\n"), {}, 0
    for t, words in data.get("synced") or []:
        if not plain(words):
            continue
        for k in range(j, min(len(lines), j + 8)):
            if plain(lines[k]) == plain(words):
                out[k], j = float(t), k + 1
                break
    return out


def events(song, kind, shift=0, simple=False):
    """What goes over the lyrics: [(from, to, name)] in time order, or None if there's nothing.
    The bass's notes without repeats (E E E C# -> E C#)."""
    if kind == "chords":
        data = chords_mod.load(song)
        found = [(c["from"], c["to"], chord_name(c["name"], shift, simple)) for c in (data or {}).get("chords", [])]
    elif kind == "bass":
        data = notes_mod.load(song)
        found = [(n["from"], n["to"], SHARPS[(n["midi"] + shift) % 12])
                 for n in ((data or {}).get("bass") or {}).get("notes", [])]
    else:
        return None
    out = []
    for start, stop, name in sorted(found):
        if out and out[-1][2] == name:
            out[-1] = (out[-1][0], stop, name)
        else:
            out.append((start, stop, name))
    return out or None


def click_for(song):
    data = chords_mod.load(song)
    return (data or {}).get("click") or chords_mod.click_of(str(song))


def bar_length(click):
    beats = int(re.match(r"\d+", click["meter"]).group()) if re.match(r"\d+", click.get("meter") or "") else 4
    return 60 / click["bpm"] * beats


def bar_cells(found, click, start, stop):
    """The bars from the one starting nearest to start up to the one ending nearest to stop:
    [(bar start, [names sounding in it])]. A bar with nothing has []."""
    length = bar_length(click)
    first = max(0, round((start - click["first"]) / length))
    last = math.ceil((stop - click["first"]) / length - 0.25)  # a bar mostly before stop counts
    out = []
    for n in range(first, last):
        a = click["first"] + n * length
        b = a + length
        names = []
        for f, t, name in found:
            # What sounds for at least a quarter of a beat inside the bar.
            if min(t, b) - max(f, a) > length / 16 and (not names or names[-1] != name):
                names.append(name)
        out.append((a, names))
    return out


def trim_silence(cells):
    """No bars of nothing (or only N.C.) at the start or the end of the song."""
    empty = lambda names: not [n for n in names if n != chords_mod.NO_CHORD]
    while cells and empty(cells[0][1]):
        cells = cells[1:]
    while cells and empty(cells[-1][1]):
        cells = cells[:-1]
    return cells


def word_start(line, pos):
    """The start of the word at pos (or of the next word, if pos falls between words)."""
    pos = max(0, min(pos, len(line)))
    if pos < len(line) and line[pos].isspace():
        while pos < len(line) and line[pos].isspace():
            pos += 1
        return pos
    while pos > 0 and not line[pos - 1].isspace():
        pos -= 1
    return pos


def place(line, start, span, found):
    """Where each chord of this line goes: [(character position, name)]. The one sounding when
    the line starts (or changing just before) goes on its first word; each change during the
    line, over the word sung then."""
    out = []
    sounding = [name for f, t, name in found if f <= start + LEAD and t > start + LEAD]
    if sounding:
        out.append((word_start(line, 0), sounding[0]))
    for f, t, name in found:
        if start + LEAD < f < start + span:
            pos = word_start(line, math.floor((f - start) / span * len(line)))
            if out and out[-1][1] == name:
                continue
            if out and len(out) == 1 and pos <= out[0][0] and sounding:
                out.pop()  # it changes on the first word: the one before was still the last line's
            out.append((max(pos, out[-1][0] if out else 0), name))
    return out


def layout(data, found, click, bars=4):
    """The sheet as rows: ("line", line number, [(position, name)]), ("bars", [(start, names)]),
    or ("plain", line number) for lines without a time. data is the lyrics (None: no lyrics)."""
    if not found:
        return [("plain", i) for i in range(len(data["text"].split("\n")))] if data else []
    end = max(t for _, t, _ in found)
    times = line_times(data) if data else {}
    if not times or not click:
        cells = trim_silence(bar_cells(found, click, 0, end)) if click else []
        return [("bars", cells[i:i + bars]) for i in range(0, len(cells), bars)]
    lines = data["text"].split("\n")
    timed = sorted(times)
    rows = []
    length = bar_length(click)

    def gap(a, b, edge=False):
        """The bars where nobody sings, or None if it's too short for a row of its own."""
        cells = bar_cells(found, click, a, b)
        if edge:
            cells = trim_silence(cells)
        if not cells or (len(cells) < 2 and not edge):
            return None
        return [("bars", cells[i:i + bars]) for i in range(0, len(cells), bars)]

    rows += gap(0, times[timed[0]], edge=True) or []
    for i, line in enumerate(lines):
        if i not in times:
            rows.append(("plain", i))
            continue
        start = times[i]
        later = [times[k] for k in timed if k > i and times[k] > start]
        following = later[0] if later else end
        span = min(max(SHORTEST, min(LONGEST, PER_LETTER * len(line.strip()))), max(following - start, 0.01))
        if not line.strip():
            span = 0.01
        placed = place(line, start, span, found) if line.strip() else []
        # The changes after the line is sung, before the next one: a row of bars if there are
        # a couple of bars of them, else at the end of the line.
        sung_until = start + span
        after = gap(sung_until, following, edge=not later) if following - sung_until > length else None
        if after is None:
            for f, t, name in found:
                if sung_until <= f < following - LEAD and (not placed or placed[-1][1] != name):
                    placed.append((len(line), name))
        if line.strip() or placed:
            rows.append(("line", i, placed))
        rows += after or []
    return rows


def clock(seconds):
    seconds = max(0, int(seconds))
    return f"{seconds // 60}:{seconds % 60:02d}"


STYLE = """
  .sheet .l.with { margin-top: .2em; }
  .seg { display: inline-flex; flex-direction: column; vertical-align: bottom; }
  .seg .c { font-weight: 700; color: #1d6b55; font-size: .92em; line-height: 1.15; min-height: 1.15em; padding-right: .35em; white-space: nowrap; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
  .seg .w { white-space: pre-wrap; min-height: 1.5em; }
  .bars { display: flex; align-items: baseline; gap: 8px; margin: .3em 0 .5em; break-inside: avoid; }
  .bars .at { font-size: 8.5pt; color: #888; width: 2.8em; text-align: right; font-variant-numeric: tabular-nums; }
  .bars .row { flex: 1; display: grid; grid-template-columns: repeat(var(--n), 1fr); border-left: 2px solid #333; }
  .bars .bar { border-right: 2px solid #333; padding: 0 .5em; font-weight: 700; color: #1d6b55; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
  .bars .bar.none { border-right-color: transparent; }
"""


def section(data, found, click, bars=4):
    """The lyrics (with their highlights and notes) and the chords over them, as HTML; everything
    shown escaped. found: from events()."""
    rows = layout(data, found, click, bars)
    lines = data["text"].split("\n") if data else []
    by_line = {}
    for m in (data or {}).get("marks", []):
        by_line.setdefault(m["line"], []).append(m)
    notes = (data or {}).get("notes", {})
    body = []
    for row in rows:
        if row[0] == "bars":
            cells = row[1]
            items = "".join(f'<span class="bar">{escape(" ".join(names)) or "&nbsp;"}</span>' for _, names in cells)
            items += '<span class="bar none"></span>' * (bars - len(cells))
            body.append(f'<div class="bars"><span class="at">{clock(cells[0][0])}</span>'
                        f'<span class="row" style="--n:{bars}">{items}</span></div>')
            continue
        i = row[1]
        line = lines[i]
        marks = by_line.get(i, [])
        note = notes.get(str(i))
        note_html = f'<span class="note">{escape(note)}</span>' if note else ""
        placed = row[2] if row[0] == "line" else []
        if not placed:
            spans = text_html(line, marks, 0, len(line))
            body.append(f'<div class="l">{spans or "&nbsp;"}{note_html}</div>')
            continue
        cuts = [p for p, _ in placed]
        segs = []
        if cuts[0] > 0:
            segs.append(f'<span class="seg"><b class="c"></b><span class="w">{text_html(line, marks, 0, cuts[0])}</span></span>')
        for k, (pos, name) in enumerate(placed):
            stop = cuts[k + 1] if k + 1 < len(cuts) else len(line)
            segs.append(f'<span class="seg"><b class="c">{escape(name)}</b>'
                        f'<span class="w">{text_html(line, marks, pos, stop)}</span></span>')
        body.append(f'<div class="l with">{"".join(segs)}{note_html}</div>')
    legend = "".join(f'<span><mark style="background:{lyrics_mod.SHADES[c]}">&nbsp;&nbsp;&nbsp;</mark> {escape(v)}</span>'
                     for c, v in (data or {}).get("legend", {}).items() if c in lyrics_mod.SHADES)
    return (f'<div class="legend">{legend}</div>\n' if legend else "") + \
        '<div class="lyrics sheet">\n' + "\n".join(body) + "\n</div>"


def text_html(line, marks, start, stop):
    """Characters start..stop of a line, with their highlights."""
    part = line[start:stop]
    shifted = [{**m, "from": max(0, m["from"] - start), "to": min(len(part), m["to"] - start)}
               for m in marks if m["to"] > start and m["from"] < stop]
    return "".join(f'<mark style="background:{lyrics_mod.SHADES[c]}">{escape(t)}</mark>' if c else escape(t)
                   for t, c in lyrics_mod.runs(part, shifted))


# "song-wizard", small and very light, repeated across every page (on screen and on paper: a fixed
# element is repeated on each printed page). An SVG pattern, not a background image: browsers
# leave backgrounds out when printing unless asked.
WATERMARK_STYLE = """
  .wm { position: fixed; inset: 0; width: 100%; height: 100%; z-index: -1; pointer-events: none; }
  .wm text { font: 600 11px system-ui, -apple-system, "Segoe UI", sans-serif; fill: #000; fill-opacity: .06; letter-spacing: .04em; }
"""
WATERMARK = ('<svg class="wm" aria-hidden="true"><defs><pattern id="wm" width="250" height="120" patternUnits="userSpaceOnUse">'
             '<text x="10" y="40">song-wizard</text><text x="135" y="100">song-wizard</text></pattern></defs>'
             '<rect width="100%" height="100%" fill="url(#wm)"/></svg>')

def logo():
    """song-wizard's icon, inside the page (a saved page has nothing else to load it from)."""
    data = resources.files("song_wizard").joinpath("static", "logo.png").read_bytes()
    return "data:image/png;base64," + base64.b64encode(data).decode()


def file_title(title, artist=None, what="drum tab"):
    """The page's title, which the browser offers as the PDF's name ("Artist - Song - lyrics by
    song-wizard"): without the characters a file name can't have (a "/" in it makes the browser
    offer something else), and "&" as "and". Only the name: the heading keeps the title as it is."""
    name = f"{artist} - {title} - {what} by song-wizard" if artist else f"{title} - {what} by song-wizard"
    name = re.sub(r"\s*&\s*", " and ", name)  # some browsers give up on it too
    return re.sub(r"\s+", " ", re.sub(r'[\\/:*?"<>|]+', "-", name)).strip()


# Printed like the drum sheet: the page has no margins of its own, so the browser adds no date,
# address or title around it; the margins are the body's, repeated on every page (clone), and
# "... by song-wizard" goes at the foot of each one (a fixed element repeats on every page).
PRINT_STYLE = """
  @page { size: A4; margin: 0; }
  .heading { display: grid; grid-template-columns: 18mm 1fr 18mm; align-items: center; margin: 0 0 4mm; }
  .heading img { width: 13mm; height: 13mm; }
  .heading .titles { text-align: center; }
  .heading h1 { font: 600 21pt/1.15 Georgia, "Times New Roman", serif; margin: 0; }
  .heading .artist { font: italic 13pt/1.3 Georgia, "Times New Roman", serif; margin-top: 1mm; }
  .heading .meta { margin: 1mm 0 0; }
  .by { display: none; }
  @media print {
    body { padding: 12mm 13mm 14mm; -webkit-box-decoration-break: clone; box-decoration-break: clone; }
    .by { display: block; position: fixed; left: 13mm; bottom: 6mm; font-size: 8pt; color: #888; }
  }
"""


def heading(title, artist=None, extra=""):
    """The first page's heading: the icon, and the title centered with the artist under it."""
    return (f'<header class="heading"><img src="{logo()}" alt=""><div class="titles"><h1>{escape(title)}</h1>'
            + (f'<div class="artist">{escape(artist)}</div>' if artist else "") + extra + "</div><span></span></header>")


def by(what):
    return f'<div class="by">{escape(what)} by song-wizard</div>'


# The choices above the sheet: never printed, and left out of a page saved to a file (they ask
# the interface for the page again).
CONTROLS_STYLE = """
  .opts { font-size: 11pt; border: 1px solid #ccc; border-radius: 8px; padding: 10px 14px; margin: 0 0 18px; background: #f6f6f3; display: flex; flex-wrap: wrap; gap: 8px 22px; align-items: center; }
  .opts label { display: inline-flex; gap: 5px; align-items: center; }
  .opts .off { color: #888; }
  .opts .muted { color: #666; font-size: 10pt; flex-basis: 100%; }
  .notice { font-size: 11pt; background: #fff4cc; border: 1px solid #e0c060; border-radius: 8px; padding: 8px 12px; margin: 0 0 16px; }
  @media print { .opts, .notice { display: none; } }
"""


def controls(hidden, lang, kind=None, have=(), shift=None, simple=False, bars=4, action="/lyrics", chords_on=False):
    """The form of choices; each change asks for the page again. hidden: [(name, value)] that
    the page needs to come back the same (the song's path, the language...). kind None: no
    "what to print" (the setlist: chords or not, by a checkbox)."""
    fields = "".join(f'<input type="hidden" name="{escape(k)}" value="{escape(str(v))}">' for k, v in hidden)
    parts = []
    if kind is not None:
        names = {"lyrics": say(lang, "sheet.only_lyrics"), "chords": say(lang, "sheet.with_chords"), "bass": say(lang, "sheet.with_bass")}
        missing = {"lyrics": say(lang, "sheet.no_lyrics_yet"), "chords": say(lang, "sheet.no_chords_yet"), "bass": say(lang, "sheet.no_bass_yet")}
        for k in KINDS:
            on = k in have
            parts.append(f'<label class="{"" if on else "off"}"><input type="radio" name="with" value="{k}"'
                         f'{" checked" if k == kind else ""}{"" if on else " disabled"}> {escape(names[k])}'
                         + ("" if on else f' <small>{escape(missing[k])}</small>') + "</label>")
    else:
        on = "chords" in have
        parts.append(f'<label class="{"" if on else "off"}"><input type="checkbox" name="with" value="chords"'
                     f'{" checked" if on and chords_on else ""}'
                     f'{"" if on else " disabled"}> {escape(say(lang, "sheet.setlist_chords"))}</label>')
    sheet = kind != "lyrics"
    if shift is not None and sheet:
        options = "".join(f'<option value="{n}"{" selected" if n == shift else ""}>{n:+d}</option>' if n else
                          f'<option value="0"{" selected" if not shift else ""}>0</option>' for n in range(-6, 7))
        parts.append(f'<label>{escape(say(lang, "sheet.pitch"))} <select name="shift">{options}</select> '
                     f'{escape(say(lang, "sheet.semitones"))}</label>')
    if kind in (None, "chords"):
        parts.append(f'<label><input type="checkbox" name="simple" value="1"{" checked" if simple else ""}> '
                     f'{escape(say(lang, "sheet.simplify"))}</label>')
    if sheet:
        bar_options = "".join(f'<option{" selected" if n == bars else ""}>{n}</option>' for n in BARS_PER_ROW)
        parts.append(f'<label>{escape(say(lang, "sheet.bars_per_row"))} <select name="bars">{bar_options}</select></label>')
    parts.append(f'<span class="muted">{escape(say(lang, "sheet.not_printed"))}</span>')
    return (f'<form class="opts" method="get" action="{action}" onchange="this.submit()">{fields}'
            + "".join(parts) + "</form>")


def available(song, data):
    """What this song can print: lyrics, chords, bass."""
    have = set()
    if data:
        have.add("lyrics")
    if (chords_mod.load(song) or {}).get("chords"):
        have.add("chords")
    if ((notes_mod.load(song) or {}).get("bass") or {}).get("notes"):
        have.add("bass")
    return have


def notice(lang, kind, data, found, click):
    """What the page says (not printed) about how the chords could not go over the words."""
    if kind == "lyrics":
        return ""
    if not found:
        return say(lang, "sheet.no_chords_yet") if kind == "chords" else say(lang, "sheet.no_bass_yet")
    if not click:
        return say(lang, "sheet.no_click")
    if not data:
        return say(lang, "sheet.no_lyrics_bars")
    if not line_times(data):
        return say(lang, "sheet.no_times")
    return say(lang, "sheet.approximate")


def body(song, data, kind="lyrics", shift=0, simple=False, bars=4):
    """The lyrics, or the sheet with chords or the bass's notes: (html, found, click)."""
    if kind == "lyrics":
        return (lyrics_mod.section(data) if data else ""), None, None
    found, click = events(song, kind, shift, simple), click_for(song)
    if not found or not click:
        return (lyrics_mod.section(data) if data else ""), found, click
    html = section(data if data and line_times(data) else None, found, click, bars)
    if data and not line_times(data):
        html += "\n" + lyrics_mod.section(data)  # the bars, then the lyrics as they are
    return html, found, click


# What each page is, in its PDF's name and at its foot.
WHAT = {"lyrics": "lyrics", "chords": "chords", "bass": "bass notes"}


def page(title, song, data, lang="es", kind="lyrics", shift=0, simple=False, bars=4, hidden=None, artist=None):
    """The printable page of a song: its lyrics, or with the chords or the bass's notes over them.
    hidden: the form's fixed values, to show the choices (None for a page saved to a file)."""
    content, found, click = body(song, data, kind, shift, simple, bars)
    tell = notice(lang, kind, data, found, click)
    form = controls(hidden, lang, kind, available(song, data), shift, simple, bars) if hidden is not None else ""
    return f"""<!doctype html>
<html lang="{lang}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(file_title(title, artist, WHAT[kind]))}</title>
<style>
  body {{ font-family: system-ui, -apple-system, "Segoe UI", sans-serif; color: #111; background: #fff; margin: 24px auto; max-width: 760px; padding: 0 16px; }}
  .print {{ margin: 16px 0; padding: 8px 16px; font-size: 12pt; cursor: pointer; }}
{PRINT_STYLE}
  @media print {{ body {{ margin: 0; max-width: none; }} .print {{ display: none; }} }}
{lyrics_mod.STYLE}{STYLE}{CONTROLS_STYLE}{WATERMARK_STYLE}</style></head>
<body>
{WATERMARK}
{form}
{f'<p class="notice">{escape(tell)}</p>' if tell and hidden is not None else ""}
{heading(title, artist)}
{content}
<button class="print" onclick="print()">{say(lang, "print.print")}</button>
{by(WHAT[kind])}
</body></html>
"""
