"""The printable setlist of a folder."""

import numpy as np
import pytest

import synth
from test_ui import request, server, TOKEN  # noqa: F401  (the fixture)

from song_wizard import lyrics, results, setlist


@pytest.mark.parametrize("name, expected", [
    ("001 - Artist - Song (Official Video).opus", ("Song", "Artist")),
    ("12 - Song [HD].wav", ("Song", "")),
    ("Band - Tune (Remastered 2011) (Official Audio).m4a", ("Tune", "Band")),
    ("003 - Song (Live).opus", ("Song (Live)", "")),  # what the version is stays
    ("004 - A - B - C.opus", ("B - C", "A")),
    ("005 - Song - .opus", ("Song -", "")),
])
def test_title_of(name, expected):
    assert setlist.title_of(name) == expected


@pytest.mark.parametrize("seconds, text", [(None, ""), (59.6, "1:00"), (245, "4:05"), (3725, "1:02:05")])
def test_clock(seconds, text):
    assert setlist.clock(seconds) == text


@pytest.fixture
def show(tmp_path, monkeypatch):
    root = tmp_path / "music"
    folder = root / "Show"
    folder.mkdir(parents=True)
    monkeypatch.setenv("SONG_WIZARD_DIR", str(root))
    tone = synth.sine(440, 2.0)
    for name in ["002 - Band - Second <b>.wav", "001 - Band - First (Official Video).wav", "003 - Third.wav"]:
        synth.write(folder / name, tone)
    synth.write(folder / "001 - Band - First (Official Video) (drums).wav", tone)  # a stem: not a song
    results.save("key", [(str(folder / "001 - Band - First (Official Video).wav"), "Am   A minor   relative C     4/4"),
                         (str(folder / "002 - Band - Second <b>.wav"), "E    E major   relative C#m   2/4  uncertain, also: Em")])
    results.save("bpm", [(str(folder / "001 - Band - First (Official Video).wav"), "120.4 BPM  steady")])
    return root, folder


def test_run(show, capsys):
    root, folder = show
    setlist.run(str(folder))
    out = capsys.readouterr().out
    lines = [l for l in out.splitlines() if l.strip()[:2] in ("1.", "2.", "3.")]
    assert [l.split(".", 1)[1].split()[0] for l in lines] == ["First", "Second", "Third"]
    assert "Am" in lines[0] and "120" in lines[0] and "0:02" in lines[0] and "(Band)" in lines[0]
    assert "E?" in lines[1]  # an uncertain key says so
    assert "3 songs, 0:06" in out
    page = (folder / "Setlist.html").read_text()
    assert "Second &lt;b&gt;" in page and "<b>.wav" not in page  # titles are text, never HTML
    assert (folder / "Setlist.txt").read_text().startswith("Show\n")


def test_run_not_a_library_folder(show, tmp_path):
    with pytest.raises(SystemExit):
        setlist.run(str(tmp_path / "nowhere"))


def test_interface(server):  # noqa: F811
    port, root = server
    folder = root / "Show"
    folder.mkdir()
    synth.write(folder / "001 - Song.wav", synth.sine(440, 1.0))
    response, content = request(port, "GET", f"/setlist?folder=Show&t={TOKEN}", token=None)
    assert response.status == 200 and b"Song" in content and b"<title>Show - setlist by song-wizard" in content
    assert request(port, "GET", "/setlist?folder=Show", token=None)[0].status == 403
    assert request(port, "GET", "/setlist?folder=../..")[0].status == 403
    assert request(port, "GET", "/setlist?folder=Empty")[0].status == 404


@pytest.fixture
def loose(show):
    """Songs in two folders, one with lyrics."""
    root, folder = show
    other = root / "Other"
    other.mkdir()
    synth.write(other / "001 - Band - Elsewhere.wav", synth.sine(440, 3.0))
    lyrics.save(folder / "003 - Third.wav", {"text": "First line <i>\nSecond line", "legend": {"yellow": "all"},
                                             "marks": [{"line": 0, "from": 0, "to": 5, "color": "yellow"}],
                                             "notes": {"1": "softly"}})
    return root, folder, other


def test_chosen_in_the_order_given(loose):
    root, folder, other = loose
    items = setlist.chosen([folder / "003 - Third.wav", other / "001 - Band - Elsewhere.wav",
                            folder / "001 - Band - First (Official Video) (drums).wav"])  # a stem: its song
    assert [r["title"] for r in items] == ["Third", "Elsewhere", "First"]
    assert [r["n"] for r in items] == [1, 2, 3] and items[2]["key"] == "Am"
    with pytest.raises(LookupError):
        setlist.chosen([folder / "nope.wav"])


def test_page_with_lyrics(loose):
    root, folder, other = loose
    items = setlist.chosen([other / "001 - Band - Elsewhere.wav", folder / "003 - Third.wav"])
    assert "class=\"song\"" not in setlist.page("Show", items)
    page = setlist.page("Show", items, with_lyrics=True)
    assert page.count('<section class="song">') == 1  # only the one with lyrics
    assert "<span class=n>2.</span> Third" in page and " line &lt;i&gt;" in page and "softly" in page
    assert "<mark style=\"background:#ffe066\">First</mark>" in page


def test_run_songs(loose, capsys, tmp_path):
    root, folder, other = loose
    before = sorted(p.name for p in folder.iterdir())
    setlist.run([str(other / "001 - Band - Elsewhere.wav"), str(folder / "003 - Third.wav")], name="Gig")
    out = capsys.readouterr().out
    assert out.startswith("Gig\n") and "1. Elsewhere" in out and "2. Third" in out and "2 songs, 0:05" in out
    assert sorted(p.name for p in folder.iterdir()) == before  # nothing saved in the folders
    setlist.run([str(folder / "003 - Third.wav")], with_lyrics=True, out=str(tmp_path / "gig.html"))
    assert "Second line" in (tmp_path / "gig.html").read_text()
    with pytest.raises(SystemExit):
        setlist.run([str(folder / "003 - Third.wav"), str(tmp_path / "nope.wav")])


def test_run_folder_out(show, tmp_path, capsys):
    root, folder = show
    setlist.run([str(folder)], out=str(tmp_path / "s.html"))
    assert "First" in (tmp_path / "s.html").read_text() and not (folder / "Setlist.html").exists()


def test_interface_songs(server):  # noqa: F811
    port, root = server
    for name in ["A", "B"]:
        (root / name).mkdir()
        synth.write(root / name / f"001 - Song {name}.wav", synth.sine(440, 1.0))
    lyrics.save(root / "B" / "001 - Song B.wav", {"text": "la la"})
    query = "path=B/001%20-%20Song%20B.wav&path=A/001%20-%20Song%20A.wav&title=Gig%20%3Cb%3E"
    response, content = request(port, "GET", f"/setlist?{query}")
    assert response.status == 200 and b"<title>Gig -b- - setlist by song-wizard" in content
    assert content.index(b"Song B") < content.index(b"Song A") and b"la la" not in content
    assert b"la la" in request(port, "GET", f"/setlist?{query}&lyrics=1")[1]
    assert b"la la" in request(port, "GET", "/setlist?folder=B&lyrics=1")[1]
    assert request(port, "GET", "/setlist?path=../../etc/passwd")[0].status == 403
    assert request(port, "GET", "/setlist?path=A/nope.wav")[0].status == 404
    assert request(port, "GET", f"/setlist?{query}", token=None)[0].status == 403
