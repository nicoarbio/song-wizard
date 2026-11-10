"""The drum sheet: the hits of "<song>.drums.json" on the click's grid (sixteenths), written in
standard drum notation and drawn by Verovio (LGPL-3), to print in A4.

Hands up (stems up), the kick down; cymbals with x heads, the open hi-hat with a circled x. Bars
equal to the one before are folded by default: the first is written and the rest become one
"repeat the bar" sign with "×N" over it; bars where the drums don't play become one rest with
how many bars it lasts. The bars keep their numbers."""

import re
from collections import defaultdict
from html import escape

from .i18n import say
from .sheet import WATERMARK, WATERMARK_STYLE, file_title, logo

# Where each part goes on the staff, and its notehead.
POSITION = {"crash": ("A", 5, "x"), "hihat": ("G", 5, "x"), "hhopen": ("G", 5, "circle-x"), "ride": ("F", 5, "x"),
            "toms": ("E", 5, None), "snare": ("C", 5, None), "kick": ("F", 4, None)}
HANDS = frozenset(POSITION) - {"kick"}
FEET = frozenset({"kick"})
# Sixteenths a note lasts (until the next hit in its voice, within its beat) -> MusicXML type, dotted.
TYPE = {1: ("16th", False), 2: ("eighth", False), 3: ("eighth", True), 4: ("quarter", False)}
# The page's printable area (A4 with 12 mm margins), in Verovio's units.
PAGE = {"pageWidth": 1860, "pageHeight": 2560, "scale": 45, "header": "none", "footer": "none",
        "adjustPageHeight": False, "pageMarginTop": 40, "pageMarginBottom": 40, "pageMarginLeft": 30, "pageMarginRight": 30}


def meter(click):
    """(quarters per bar, numerator, denominator) of the click's meter; 4/4 if it can't be read."""
    num, _, den = str(click.get("meter") or "4/4").partition("/")
    try:
        num, den = int(num), int(den or 4)
        quarters = num * 4 / den
        if num > 0 and den in (2, 4, 8, 16) and quarters == int(quarters):
            return int(quarters), num, den
    except ValueError:
        pass
    return 4, 4, 4


def grid(data):
    """{bar: frozenset((sixteenth, part))} with the hits on the click's grid (bar 0 starts on the
    first beat; a hit before it is in bar -1), and the sixteenths in a bar."""
    click = data.get("click") or {"bpm": 120.0, "meter": "4/4", "first": 0.0}
    quarters = meter(click)[0]
    per_bar, sixteenth = quarters * 4, 60 / click["bpm"] / 4
    bars = defaultdict(set)
    for h in data.get("hits", []):
        bar, slot = divmod(round((h["t"] - click["first"]) / sixteenth), per_bar)
        bars[bar].add((slot, h["part"]))
    for content in bars.values():  # an open hi-hat is the hi-hat there
        content -= {(slot, "hihat") for slot, part in list(content) if part == "hhopen"}
    return {bar: frozenset(c) for bar, c in bars.items()}, per_bar


def items(bars, fold=True):
    """What to write, in order: ("bar", n, content), ("repeat", n, times) for bars equal to the
    one before, ("rest", n, bars) where nothing is played. n is the bar's index (0 = first beat)."""
    if not bars:
        return []
    out, b, last = [], min(min(bars), 0), max(bars)
    while b <= last:
        content = bars.get(b, frozenset())
        run = 1
        while fold and b + run <= last and bars.get(b + run, frozenset()) == content:
            run += 1
        if not content:
            out.append(("rest", b, run))
        else:
            out.append(("bar", b, content))
            if run > 1:
                out.append(("repeat", b + 1, run - 1))
        b += run
    return out


def gap(duration, number):
    """Time that passes in a voice without a rest drawn for it."""
    return f"<forward><duration>{duration}</duration><voice>{number}</voice></forward>"


def voice(content, parts, quarters, number, stem):
    """One voice of a bar in MusicXML: per beat, each hit lasting until the next, beamed within
    the beat. As drum charts are written, the kick's voice draws no rests at all, and the hands'
    only where nothing plays: a beat with just the kick is the kick's. Two empty beats in a row,
    from the bar's first or third, are one half rest."""
    feet = number == 2
    out, beat = [], 0
    played = lambda b: any(b * 4 <= s < b * 4 + 4 for s, _ in content)
    while beat < quarters:
        slots = [sorted(p for s, p in content if s == beat * 4 + i and p in parts) for i in range(4)]
        starts = [i for i in range(4) if slots[i]]
        if not starts:
            if feet or played(beat):
                out.append(gap(4, number))
            elif beat % 2 == 0 and beat + 1 < quarters and not played(beat + 1):
                out.append(f"<note><rest/><duration>8</duration><voice>{number}</voice><type>half</type></note>")
                beat += 1
            else:
                out.append(f"<note><rest/><duration>4</duration><voice>{number}</voice><type>quarter</type></note>")
            beat += 1
            continue
        if starts[0]:
            kind, dot = TYPE[starts[0]]
            out.append(gap(starts[0], number) if feet else
                       f"<note><rest/><duration>{starts[0]}</duration><voice>{number}</voice><type>{kind}</type>"
                       f"{'<dot/>' if dot else ''}</note>")
        lengths = [(starts[k + 1] if k + 1 < len(starts) else 4) - s for k, s in enumerate(starts)]
        for k, (s, d) in enumerate(zip(starts, lengths)):
            kind, dot = TYPE[d]
            beams = ""
            if len(starts) > 1:
                beams = f'<beam number="1">{"begin" if k == 0 else "end" if k == len(starts) - 1 else "continue"}</beam>'
                if d == 1:
                    before, after = k > 0 and lengths[k - 1] == 1, k + 1 < len(lengths) and lengths[k + 1] == 1
                    second = ("continue" if before and after else "end" if before else "begin" if after
                              else "forward hook" if k == 0 else "backward hook")
                    beams += f'<beam number="2">{second}</beam>'
            for j, part in enumerate(slots[s]):
                step, octave, head = POSITION[part]
                out.append(f"<note>{'<chord/>' if j else ''}<unpitched><display-step>{step}</display-step>"
                           f"<display-octave>{octave}</display-octave></unpitched><duration>{d}</duration>"
                           f"<voice>{number}</voice><type>{kind}</type>{'<dot/>' if dot else ''}<stem>{stem}</stem>"
                           + (f"<notehead>{head}</notehead>" if head else "") + (beams if j == 0 else "") + "</note>")
        beat += 1
    return "".join(out)


def musicxml(title, data, fold=True):
    click = data.get("click") or {"bpm": 120.0, "meter": "4/4", "first": 0.0}
    quarters, num, den = meter(click)
    bars, per_bar = grid(data)
    whole = quarters * 4
    rest = f'<note><rest measure="yes"/><duration>{whole}</duration><voice>1</voice></note>'
    measures, stop = [], False
    for n, (kind, b, what) in enumerate(items(bars, fold)):
        head = ""
        if n == 0:
            head = (f"<attributes><divisions>4</divisions><time><beats>{num}</beats><beat-type>{den}</beat-type></time>"
                    "<clef><sign>percussion</sign></clef></attributes>"
                    '<direction placement="above"><direction-type><metronome><beat-unit>quarter</beat-unit>'
                    f"<per-minute>{click['bpm']:.4g}</per-minute></metronome></direction-type></direction>")
        if stop:
            head += '<attributes><measure-style><measure-repeat type="stop"/></measure-style></attributes>'
            stop = False
        if kind == "bar":
            measures.append(f'<measure number="{b + 1}">{head}{voice(what, HANDS, quarters, 1, "up")}'
                            f'<backup><duration>{whole}</duration></backup>{voice(what, FEET, quarters, 2, "down")}</measure>')
        elif kind == "repeat":
            times = (f'<direction placement="above"><direction-type><words font-weight="bold">×{what}</words>'
                     "</direction-type></direction>") if what > 1 else ""
            measures.append(f'<measure number="{b + 1}">{head}<attributes><measure-style><measure-repeat type="start">1'
                            f"</measure-repeat></measure-style></attributes>{times}{rest}</measure>")
            stop = True
        else:
            several = (f"<attributes><measure-style><multiple-rest>{what}</multiple-rest></measure-style></attributes>"
                       if what > 1 else "")
            measures.append(f'<measure number="{b + 1}">{head}{several}{rest}</measure>')
            measures += [f'<measure number="{b + 1 + k}">{rest}</measure>' for k in range(1, what)]
    return ('<?xml version="1.0" encoding="UTF-8"?><score-partwise version="3.1">'
            f"<work><work-title>{escape(title)}</work-title></work>"
            '<part-list><score-part id="P1"><part-name print-object="no">Drums</part-name></score-part></part-list>'
            f'<part id="P1">{"".join(measures)}</part></score-partwise>')


def toolkit(height):
    import os

    import verovio
    # Its fonts, by path: what it finds on its own is only set up in the main thread, and the
    # interface answers in others.
    tk = verovio.toolkit(False)
    tk.setResourcePath(os.path.join(os.path.dirname(verovio.__file__), "data"))
    tk.setOptions({**PAGE, "pageHeight": height})
    return tk


def heading_mm(title, artist):
    """About how much of the first page the heading takes (title lines, the artist, the
    legend), in mm; a little more rather than less, so the music never has to shrink."""
    lines = max(1, -(-len(title) // 38))
    return 18 + 9.5 * lines + (7 if artist else 0)


def render(xml, first_height=None):
    """The sheet's pages, as SVG. The first one is shorter (first_height, in Verovio's units) to
    leave room for the heading, and the rest start where it ends: every page at the same size."""
    whole = toolkit(PAGE["pageHeight"])
    if not whole.loadData(xml):
        raise ValueError("verovio couldn't read the sheet")
    if not first_height or first_height >= PAGE["pageHeight"]:
        return [scalable(whole.renderToSVG(n)) for n in range(1, whole.getPageCount() + 1)]
    mei = whole.getMEI()
    first = toolkit(first_height)
    first.loadData(mei)
    pages = [first.renderToSVG(1)]
    if first.getPageCount() > 1:
        # The rest from the next bar (bars counted in order, as Verovio's selection does).
        shown = len(re.findall(r'class="measure"', pages[0]))
        rest = toolkit(PAGE["pageHeight"])
        rest.loadData(mei)
        rest.select({"measureRange": f"{shown + 1}-end"})
        rest.redoLayout()
        pages += [rest.renderToSVG(n) for n in range(1, rest.getPageCount() + 1)]
    return [scalable(p) for p in pages]


def scalable(svg):
    """Verovio's page with a viewBox instead of a fixed size, so it fills the room it's given
    (keeping its shape, at the top), and without its own titles: the page's is the only one."""
    svg = re.sub(r"<title\b[^>]*>.*?</title>", "", svg, flags=re.S)  # Verovio's labels ("[selectionScore]")
    m = re.match(r'\s*<svg width="([\d.]+)px" height="([\d.]+)px"', svg)
    if not m:
        return svg
    return (f'<svg viewBox="0 0 {m[1]} {m[2]}" preserveAspectRatio="xMidYMin meet"' + svg[m.end():])




STYLE = """
  @page { size: A4; margin: 0; }
  * { box-sizing: border-box; }
  body { font-family: system-ui, -apple-system, "Segoe UI", sans-serif; color: #111; background: #e9e9e4; margin: 0; }
  .bar { position: sticky; top: 0; z-index: 2; display: flex; flex-wrap: wrap; gap: 8px 18px; align-items: center; justify-content: center;
         padding: 10px 16px; background: #f6f6f3; border-bottom: 1px solid #ccc; font-size: 11pt; }
  .bar .print { padding: 7px 18px; font-size: 12pt; cursor: pointer; font-weight: 600; }
  .bar label { display: inline-flex; gap: 5px; align-items: center; }
  .bar .off { color: #888; font-size: 10pt; }
  .notice { max-width: 210mm; margin: 14px auto 0; font-size: 10.5pt; background: #fff4d6; border: 1px solid #e8cf87; border-radius: 6px; padding: 8px 12px; }
  /* Each sheet is an A4 page: on screen, a sheet of paper; printed, exactly one page (with no
     margins of its own, the browser adds no date or address). */
  .sheet { width: 210mm; height: 297mm; margin: 16px auto; padding: 12mm 12mm 8mm; background: #fff; box-shadow: 0 1px 6px rgba(0,0,0,.18);
           display: flex; flex-direction: column; position: relative; overflow: hidden; }
  .sheet .music { flex: 1 1 0; min-height: 0; }
  .sheet .wm { position: absolute; z-index: 0; }
  .sheet > :not(.wm) { position: relative; z-index: 1; }
  .sheet .music svg { display: block; width: 100%; height: 100%; }
  .sheet .mRptNum { display: none; }
  header { display: grid; grid-template-columns: 22mm 1fr 22mm; align-items: center; margin-bottom: 3mm; }
  header img { width: 14mm; height: 14mm; }
  header .titles { text-align: center; }
  header h1 { font: 600 21pt/1.15 Georgia, "Times New Roman", serif; margin: 0; }
  header .artist { font: italic 13pt/1.3 Georgia, "Times New Roman", serif; margin-top: 1mm; }
  .legend { font-size: 8pt; color: #555; margin: 0 0 2mm; text-align: center; }
  footer { display: flex; justify-content: space-between; font-size: 8pt; color: #888; padding-top: 2mm; }
  @media print {
    body { background: #fff; }
    .bar, .notice { display: none; }
    .sheet { margin: 0; box-shadow: none; break-after: page; }
    .sheet:last-child { break-after: auto; }
  }
"""


def page(title, data, lang="es", fold=True, hidden=None, artist=None):
    """The printable drum sheet: A4 pages, the first with the title (and the artist under it)
    centered and the icon. hidden: the form's fixed values ([(name, value)]), to show the
    choices; None for a page saved to a file."""
    # The first page's music is shorter by the heading, so all pages keep the same size.
    first = PAGE["pageHeight"] - int(heading_mm(title, artist) * PAGE["pageWidth"] / 186)
    pages = render(musicxml(title, data, fold), first) if data.get("hits") else []
    bar = ""
    if hidden is not None:
        from urllib.parse import quote
        fields = "".join(f'<input type="hidden" name="{escape(k)}" value="{escape(str(v))}">' for k, v in hidden)
        path = dict(hidden).get("path", "")
        bar = (f'<form class="bar" method="get" action="/drums">{fields}<input type="hidden" name="fold" value="0">'
               f'<button type="button" class="print" onclick="print()">{escape(say(lang, "print.print"))}</button>'
               f'<label><input type="checkbox" name="fold" value="1"{" checked" if fold else ""} onchange="this.form.submit()"> '
               f'{escape(say(lang, "drums.fold"))}</label>'
               f'<a href="/drums.mid?path={quote(path)}" download>{escape(say(lang, "drums.midi"))}</a>'
               f'<span class="off">{escape(say(lang, "sheet.not_printed"))}</span></form>'
               f'<p class="notice">{escape(say(lang, "drums.detected_notice"))}</p>')
    elif pages:
        bar = f'<div class="bar"><button type="button" class="print" onclick="print()">{escape(say(lang, "print.print"))}</button></div>'
    header = (f'<header><img src="{logo()}" alt=""><div class="titles"><h1>{escape(title)}</h1>'
              + (f'<div class="artist">{escape(artist)}</div>' if artist else "") + "</div><span></span></header>"
              f'<p class="legend">{escape(say(lang, "drums.legend"))}</p>')
    foot = lambda n: (f"<footer><span>drum tab by song-wizard</span><span>{n} / {len(pages)}</span></footer>")
    sheets = "".join(f'<section class="sheet">{WATERMARK}{header if n == 1 else ""}<div class="music">{svg}</div>{foot(n)}</section>'
                     for n, svg in enumerate(pages, 1))
    if not pages:
        sheets = f'<section class="sheet">{WATERMARK}{header}<p>{escape(say(lang, "drums.none"))}</p></section>'
    return f"""<!doctype html>
<html lang="{lang}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(file_title(title, artist))}</title>
<style>{WATERMARK_STYLE}{STYLE}</style></head>
<body>
{bar}
{sheets}
</body></html>
"""
