"""The printable setlist of a folder."""

import numpy as np
import pytest

import synth
from test_ui import request, server, TOKEN  # noqa: F401  (the fixture)

from song_wizard import results, setlist


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
    assert response.status == 200 and b"Song" in content and b"<title>Setlist: Show" in content
    assert request(port, "GET", "/setlist?folder=Show", token=None)[0].status == 403
    assert request(port, "GET", "/setlist?folder=../..")[0].status == 403
    assert request(port, "GET", "/setlist?folder=Empty")[0].status == 404
