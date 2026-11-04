"""The drum sheet: the hits of "<song>.drums.json" on the click's grid (sixteenths), written in
standard drum notation and drawn by Verovio (LGPL-3), to print in A4.

Hands up (stems up), the kick down; cymbals with x heads, the open hi-hat with a circled x. Bars
equal to the one before are folded by default: the first is written and the rest become one
"repeat the bar" sign with "×N" over it; bars where the drums don't play become one rest with
how many bars it lasts. The bars keep their numbers."""

from collections import defaultdict
from html import escape

from .i18n import say
from .sheet import CONTROLS_STYLE, WATERMARK, WATERMARK_STYLE

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


def voice(content, parts, quarters, number, stem):
    """One voice of a bar in MusicXML: per beat, each hit lasting until the next (rests only
    before the first), beamed within the beat."""
    out = []
    for beat in range(quarters):
        slots = [sorted(p for s, p in content if s == beat * 4 + i and p in parts) for i in range(4)]
        starts = [i for i in range(4) if slots[i]]
        if not starts:
            out.append(f"<note><rest/><duration>4</duration><voice>{number}</voice><type>quarter</type></note>")
            continue
        if starts[0]:
            kind, dot = TYPE[starts[0]]
            out.append(f"<note><rest/><duration>{starts[0]}</duration><voice>{number}</voice><type>{kind}</type>"
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


def render(xml):
    """The sheet's pages, as SVG."""
    import os

    import verovio
    # Its fonts, by path: what it finds on its own is only set up in the main thread, and the
    # interface answers in others.
    toolkit = verovio.toolkit(False)
    toolkit.setResourcePath(os.path.join(os.path.dirname(verovio.__file__), "data"))
    toolkit.setOptions(PAGE)
    if not toolkit.loadData(xml):
        raise ValueError("verovio couldn't read the sheet")
    return [toolkit.renderToSVG(page) for page in range(1, toolkit.getPageCount() + 1)]


STYLE = """
  .pages svg { display: block; width: 100%; height: auto; }
  .pages .page + .page { break-before: page; margin-top: 24px; }
  /* Each of Verovio's pages fits on a sheet (the first one with the legend above it). */
  @media print { .pages svg { width: auto; max-width: 100%; max-height: 262mm; margin: 0 auto; }
                 .pages .page:first-child svg { max-height: 245mm; } .pages .page + .page { margin-top: 0; } }
  .mRptNum { display: none; }
  h1 { font-size: 18pt; margin: 0 0 4px; }
  .legend { font-size: 9pt; color: #444; margin: 0 0 6px; }
  .notice { font-size: 11pt; background: #fff4d6; border: 1px solid #e8cf87; border-radius: 6px; padding: 8px 12px; }
  @media print { .notice { display: none; } }
"""


def page(title, data, lang="es", fold=True, hidden=None):
    """The printable drum sheet. hidden: the form's fixed values ([(name, value)]), to show the
    choices; None for a page saved to a file."""
    pages = render(musicxml(title, data, fold)) if data.get("hits") else []
    form = ""
    if hidden is not None:
        fields = "".join(f'<input type="hidden" name="{escape(k)}" value="{escape(str(v))}">' for k, v in hidden)
        path = dict(hidden).get("path", "")
        from urllib.parse import quote
        form = (f'<form class="opts" method="get" action="/drums">{fields}<input type="hidden" name="fold" value="0">'
                f'<label><input type="checkbox" name="fold" value="1"{" checked" if fold else ""} onchange="this.form.submit()"> '
                f'{escape(say(lang, "drums.fold"))}</label>'
                f'<a href="/drums.mid?path={quote(path)}" download>{escape(say(lang, "drums.midi"))}</a>'
                f'<span class="off">{escape(say(lang, "sheet.not_printed"))}</span></form>')
    notice = (f'<p class="notice">{escape(say(lang, "drums.detected_notice"))}</p>' if hidden is not None else "")
    body = ("".join(f'<div class="page">{svg}</div>' for svg in pages) if pages
            else f"<p>{escape(say(lang, 'drums.none'))}</p>")
    return f"""<!doctype html>
<html lang="{lang}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(say(lang, "drums.title", name=title))}</title>
<style>
  @page {{ size: A4; margin: 12mm; }}
  body {{ font-family: system-ui, -apple-system, "Segoe UI", sans-serif; color: #111; background: #fff; margin: 24px auto; max-width: 820px; padding: 0 16px; }}
  .print {{ margin: 16px 0; padding: 8px 16px; font-size: 12pt; cursor: pointer; }}
  @media print {{ body {{ margin: 0; max-width: none; padding: 0; }} .print, .opts {{ display: none; }} }}
{CONTROLS_STYLE}{WATERMARK_STYLE}{STYLE}</style></head>
<body>
{WATERMARK}
{form}
{notice}
<h1>{escape(title)}</h1>
<p class="legend">{escape(say(lang, "drums.legend"))}</p>
<div class="pages">{body}</div>
<button class="print" onclick="print()">{say(lang, "print.print")}</button>
</body></html>
"""
