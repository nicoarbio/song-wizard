"""The chord sheet: chords (or the bass's notes) over the lyrics' words, rows of bars where nobody
sings or when the lyrics have no times, names moved and simplified, the choices on the page,
the setlist with chords, and the watermark on every printed page."""

import urllib.parse

import pytest

import synth
from test_ui import request, server  # noqa: F401  (the fixture)

from song_wizard import chords, lyrics, notes, rename, results, setlist, sheet

# 120 BPM in 4/4 from 0: a bar is 2 s.
CLICK = {"bpm": 120.0, "meter": "4/4", "first": 0.0}


@pytest.mark.parametrize("name, shift, simple, shown", [
    ("Am7", 0, False, "Am7"), ("Am7", 2, False, "Bm7"), ("Bb", 1, False, "B"), ("Eb", -1, False, "D"),
    ("C#m7b5", 0, True, "C#m"), ("A7", 0, True, "A"), ("G/B", 2, False, "A/C#"), ("Bbmaj7", 2, True, "C"),
    ("N.C.", 3, False, "N.C."), ("whatever", 2, False, "whatever"),
])
def test_chord_name(name, shift, simple, shown):
    assert sheet.chord_name(name, shift, simple) == shown


@pytest.mark.parametrize("pos, start", [(0, 0), (2, 0), (5, 6), (6, 6), (8, 6), (30, 13)])
def test_word_start(pos, start):
    assert sheet.word_start("Hello world, again", pos) == start


def test_place_over_the_words():
    line = "one two three four"  # 18 letters: sung in 5.4 s
    found = [(0, 2, "A"), (2, 3, "D"), (3, 9, "E")]
    placed = sheet.place(line, 0.0, 5.4, found)
    # A from the start; D at 2 s = letter 6 ("two" starts at 4); E at 3 s = letter 10 ("three").
    assert placed == [(0, "A"), (4, "D"), (8, "E")]


def test_place_a_change_on_the_first_word_replaces_the_one_before():
    assert sheet.place("la la la", 10.0, 3.0, [(0, 10.1, "A"), (10.1, 20, "B")]) == [(0, "B")]


def test_line_times_from_the_database_lines():
    data = {"text": "Intro\nfirst line\n\nsecond line", "synced": [[1.0, "First line"], [5.0, "second line!"]]}
    assert sheet.line_times(data) == {1: 1.0, 3: 5.0}
    assert sheet.line_times({**data, "times": {"0": 0.5}}) == {0: 0.5}  # set by hand wins


def test_layout_bars_where_nobody_sings():
    data = {"text": "one two three\nfour five six", "times": {"0": 8.0, "1": 20.0}}
    found = [(0, 4, "N.C."), (4, 8, "E"), (8, 14, "A"), (14, 20, "B"), (20, 30, "E")]
    rows = sheet.layout(data, found, CLICK, bars=2)
    kinds = [r[0] for r in rows]
    # Intro: the silent bars left out, then E E; the first line; its gap (12 s to 20 s) in bars;
    # the last line, and the end in bars.
    assert rows[0] == ("bars", [(4.0, ["E"]), (6.0, ["E"])])
    assert kinds == ["bars", "line", "bars", "bars", "line", "bars", "bars"]
    assert rows[1] == ("line", 0, [(0, "A")])
    assert [names for _, names in rows[2][1] + rows[3][1]] == [["A"], ["B"], ["B"], ["B"]]
    assert all(len(r[1]) <= 2 for r in rows if r[0] == "bars")


def test_layout_without_times_is_all_bars():
    rows = sheet.layout({"text": "la\nla"}, [(0, 4, "E"), (4, 8, "A"), (8, 9, "B")], CLICK, bars=4)
    assert rows == [("bars", [(0.0, ["E"]), (2.0, ["E"]), (4.0, ["A"]), (6.0, ["A"])]), ("bars", [(8.0, ["B"])])]


def test_section_escapes_and_keeps_marks():
    data = {"text": "<b>bold</b> words", "times": {"0": 0.0},
            "marks": [{"line": 0, "from": 0, "to": 3, "color": "pink"}], "notes": {"0": "<i>softly"}}
    html = sheet.section(data, [(0, 10, "A<x>")], CLICK)
    assert "<b>bold" not in html and "&lt;b&gt;" in html and "A&lt;x&gt;" in html and "&lt;i&gt;softly" in html
    assert 'background:#fcc2d7' in html
    rows = sheet.section(None, [(0, 4, "E")], CLICK, bars=2)
    assert '<span class="row" style="--n:2">' in rows and rows.count('class="bar none"') == 0


@pytest.fixture
def song(tmp_path):
    path = synth.song(tmp_path / "Show", "001 - Song.wav", synth.sine(440, 1.0))
    chords.save(path, {"chords": [{"from": 0, "to": 4, "name": "Am"}, {"from": 4, "to": 8, "name": "G7"}], "click": CLICK})
    notes.save(path, {"bass": {"notes": [{"from": 0, "to": 1, "midi": 45}, {"from": 1, "to": 2, "midi": 45},
                                         {"from": 2, "to": 4, "midi": 43}]}})
    return path


def test_events(song):
    assert sheet.events(song, "chords", 2) == [(0, 4, "Bm"), (4, 8, "A7")]
    assert sheet.events(song, "chords", 0, simple=True) == [(0, 4, "Am"), (4, 8, "G")]
    assert sheet.events(song, "bass") == [(0, 2, "A"), (2, 4, "G")]  # A A G -> A G


def test_page_choices_and_watermark(song):
    page = sheet.page("Song", song, None, kind="chords", hidden=[("path", "Show/001 - Song.wav")])
    assert 'class="wm"' in page and "song-wizard" in page
    assert 'name="with" value="chords" checked' in page and 'value="lyrics" disabled' in page
    assert "Am" in page and "G7" in page and "<p class=\"notice\">" in page  # no lyrics: in bars, and it says so
    assert '<form class="opts"' not in sheet.page("Song", song, None, kind="chords")  # saved to a file: no choices
    lyrics.save(song, {"text": "la la"})
    page = sheet.page("Song", song, lyrics.load(song), kind="chords", hidden=[])
    assert "la la" in page and "<p class=\"notice\">" in page  # no times: bars, then the lyrics


def test_export_and_rename(song):
    lyrics.save(song, {"text": "la la la", "times": {"0": 0.0}})
    out = lyrics.export(song, "chords", shift=2)
    assert out.name == "001 - Song.chords.html" and "Bm" in out.read_text(encoding="utf-8")
    assert lyrics.export(song, "bass").name == "001 - Song.bass.html"
    rename.run(str(song), "Other")
    other = song.parent.parent / "001 - Other"
    assert (other / "001 - Other.chords.html").exists() and (other / "001 - Other.bass.html").exists()


def test_interface(server):  # noqa: F811
    port, root = server
    path = synth.song(root / "Show", "001 - Song.wav", synth.sine(440, 1.0))
    q = urllib.parse.quote("Show/001 - Song/001 - Song.wav")
    assert request(port, "GET", f"/lyrics?path={q}")[0].status == 404  # nothing to print yet
    chords.save(path, {"chords": [{"from": 0, "to": 4, "name": "Am"}], "click": CLICK})
    response, content = request(port, "GET", f"/lyrics?path={q}")  # no lyrics: the chords, in bars
    assert response.status == 200 and b"Am" in content and b'class="wm"' in content
    lyrics.save(path, {"text": "la la", "times": {"0": 0.0}})
    content = request(port, "GET", f"/lyrics?path={q}&with=chords&shift=3&bars=2&simple=1")[1]
    assert b">Cm</b>" in content and b'<option selected>2</option>' in content
    content = request(port, "GET", f"/lyrics?path={q}&with=nope&shift=x&bars=9")[1]
    assert b">Am</b>" not in content and b"la la" in content  # back to the defaults: just the lyrics


def test_setlist_with_chords(tmp_path, monkeypatch):
    root = tmp_path / "music"
    folder = root / "Show"
    folder.mkdir(parents=True)
    monkeypatch.setenv("SONG_WIZARD_DIR", str(root))
    for name in ["001 - One.wav", "002 - Two.wav"]:
        synth.song(folder, name, synth.sine(440, 1.0))
    chords.save(folder / "001 - One", {"chords": [{"from": 0, "to": 4, "name": "Am"}], "click": CLICK})
    results.save(folder / "001 - One", "tempo", "120.00 BPM 4/4, first beat 0.000 s")
    lyrics.save(folder / "002 - Two", {"text": "only words"})
    items = setlist.rows(*setlist.find(folder))
    page = setlist.page("Show", items, with_lyrics=True)
    assert page.count('<section class="song">') == 1 and "only words" in page and ">Am<" not in page
    page = setlist.page("Show", items, with_lyrics=True, with_chords=True, hidden=[("folder", "Show")])
    assert page.count('<section class="song">') == 2 and "Am" in page and 'class="wm"' in page
    assert 'name="with" value="chords" checked' in page
