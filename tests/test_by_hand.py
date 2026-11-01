"""Key and tempo typed in by hand, over what was detected."""

import json

import pytest

import synth
from test_ui import get_json, request, server  # noqa: F401  (the fixture)

from song_wizard import bpm, key, results


@pytest.mark.parametrize("text, expected", [
    ("Am", ("A", "minor")), ("a minor", ("A", "minor")), ("C#", ("C#", "major")), ("Db", ("C#", "major")),
    ("Bb major", ("Bb", "major")), ("A#", ("Bb", "major")), ("G#m", ("G#", "minor")), ("Abm", ("G#", "minor")),
    ("La menor", ("A", "minor")), ("sib", ("Bb", "major")), ("Fa#m", ("F#", "minor")), ("Do mayor", ("C", "major")),
    ("solm", ("G", "minor")), ("Cb", ("B", "major")),
])
def test_parse_key(text, expected):
    assert key.parse(text) == expected


@pytest.mark.parametrize("text", ["", "H", "A minor please", "120", "Am7", "re#bm"])
def test_parse_key_invalid(text):
    assert key.parse(text) is None


@pytest.mark.parametrize("text, expected", [("120", 120.0), ("98.5", 98.5), ("98,5", 98.5), ("120 BPM", 120.0),
                                            ("20", 20.0), ("400", 400.0)])
def test_parse_tempo(text, expected):
    assert bpm.parse(text) == expected


@pytest.mark.parametrize("text", ["", "fast", "19", "401", "0", "-120", "1e3"])
def test_parse_tempo_invalid(text):
    assert bpm.parse(text) is None


def test_set_by_hand_and_detection_keeps_it(tmp_path, capsys):
    song = tmp_path / "Song.wav"
    synth.write(song, synth.drum_song(120, 8))
    key.run([str(song)], value="La menor")
    bpm.run([str(song)], value="121,5")
    lines = {c: results.read(str(tmp_path), c)["Song.wav"] for c in ("key", "bpm")}
    assert lines["key"].split()[:3] == ["Am", "A", "minor"] and lines["key"].endswith(results.HAND)
    assert lines["bpm"] == f"121.5 BPM  {results.HAND}"
    # Detecting again leaves them alone (and doesn't even read the audio)...
    key.run([str(song)])
    bpm.run([str(song)])
    assert {c: results.read(str(tmp_path), c)["Song.wav"] for c in ("key", "bpm")} == lines
    assert "--force" in capsys.readouterr().out
    # ...unless forced.
    bpm.run([str(song)], force=True)
    assert not results.read(str(tmp_path), "bpm")["Song.wav"].endswith(results.HAND)


def test_set_by_hand_invalid(tmp_path):
    song = tmp_path / "Song.wav"
    song.write_bytes(b"x")
    with pytest.raises(SystemExit):
        key.run([str(song)], value="H")
    with pytest.raises(SystemExit):
        bpm.run([str(song)], value="500")
    assert not (tmp_path / "key.txt").exists() and not (tmp_path / "bpm.txt").exists()


def test_tempo_by_hand_warns_about_the_practice_click(tmp_path, capsys):
    song = tmp_path / "Song.wav"
    song.write_bytes(b"x")
    results.save("click", [(str(song), "100.00 BPM 4/4, first beat 0.500 s")])
    bpm.run([str(song)], value="100.2")
    assert "practice click" not in capsys.readouterr().out
    bpm.run([str(song)], value="120")
    assert "practice click is still at 100.00 BPM" in capsys.readouterr().out


def test_interface(server, monkeypatch):  # noqa: F811
    port, root = server
    (root / "001 - Song.opus").write_bytes(b"x")
    response, content = request(port, "POST", "/api/set-result", {"path": "001 - Song.opus", "what": "key", "value": "Fa#m"})
    assert response.status == 200 and json.loads(content)["text"].startswith("F#m")
    response, content = request(port, "POST", "/api/set-result", {"path": "001 - Song.opus", "what": "bpm", "value": "98.5"})
    assert json.loads(content) == {"text": f"98.5 BPM  {results.HAND}", "note": None}
    (song,) = get_json(port, "/api/library")["folders"][0]["songs"]
    assert song["key"].startswith("F#m") and song["bpm"] == f"98.5 BPM  {results.HAND}"
    # A saved practice click at another tempo is pointed out.
    results.save("click", [(str(root / "001 - Song.opus"), "98.50 BPM 4/4, first beat 0.500 s")])
    content = request(port, "POST", "/api/set-result", {"path": "001 - Song.opus", "what": "bpm", "value": "140"})[1]
    assert "click" in json.loads(content)["note"]
    for bad in [{"what": "key", "value": "H"}, {"what": "bpm", "value": "fast"}, {"what": "click", "value": "1"}, {"what": "key"}]:
        response, content = request(port, "POST", "/api/set-result", {"path": "001 - Song.opus", **bad})
        assert response.status == 400
    assert "no es una tonalidad" in json.loads(request(port, "POST", "/api/set-result",
                                                       {"path": "001 - Song.opus", "what": "key", "value": "H"})[1])["error"]
    assert request(port, "POST", "/api/set-result", {"path": "../x.opus", "what": "key", "value": "Am"})[0].status == 403
    assert request(port, "POST", "/api/set-result", {"path": "none.opus", "what": "key", "value": "Am"})[0].status == 404
