"""Key and tempo typed in by hand, over what was detected."""

import json
import os

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
    song = synth.song(tmp_path, "Song.wav", synth.drum_song(120, 8))
    key.run([str(song)], value="La menor")
    bpm.run([str(song)], value="121,5")
    lines = {c: results.read(song, c) for c in ("key", "tempo")}
    assert lines["key"].split()[:3] == ["Am", "A", "minor"] and lines["key"].endswith(results.HAND)
    assert lines["tempo"] == f"121.5 BPM  {results.HAND}"
    # Detecting again leaves them alone (and doesn't even read the audio)...
    key.run([str(song)])
    bpm.run([str(song)])
    assert {c: results.read(song, c) for c in ("key", "tempo")} == lines
    assert "--force" in capsys.readouterr().out
    # ...unless forced.
    bpm.run([str(song)], force=True)
    assert not results.read(song, "tempo").endswith(results.HAND)


def test_set_by_hand_invalid(tmp_path):
    (tmp_path / "Song").mkdir()
    song = tmp_path / "Song" / "Song.wav"
    song.write_bytes(b"x")
    with pytest.raises(SystemExit):
        key.run([str(song)], value="H")
    with pytest.raises(SystemExit):
        bpm.run([str(song)], value="500")
    assert os.listdir(song.parent) == ["Song.wav"]


def test_one_tempo_where_the_beats_fall_stays(tmp_path, capsys):
    """A tempo typed in over the practice click's: the click follows it, from the same first beat."""
    (tmp_path / "Song").mkdir()
    song = tmp_path / "Song" / "Song.wav"
    song.write_bytes(b"x")
    results.save(song, "tempo", "100.00 BPM 4/4, first beat 0.500 s")
    bpm.run([str(song)], value="120")
    assert results.read(song, "tempo") == f"120.00 BPM 4/4, first beat 0.500 s  {results.HAND}"
    bpm.run([str(song)])  # detecting doesn't replace it
    assert results.read(song, "tempo") == f"120.00 BPM 4/4, first beat 0.500 s  {results.HAND}"


def test_detecting_keeps_where_the_beats_fall(tmp_path, capsys):
    song = synth.song(tmp_path, "Song.wav", synth.drum_song(120, 8))
    results.save(song, "tempo", "120.10 BPM 4/4, first beat 0.010 s")  # from align: more than bpm knows
    bpm.run([str(song)])
    assert results.read(song, "tempo") == "120.10 BPM 4/4, first beat 0.010 s"
    assert "--force" in capsys.readouterr().out


def test_interface(server, monkeypatch):  # noqa: F811
    port, root = server
    (root / "001 - Song").mkdir()
    (root / "001 - Song" / "001 - Song.opus").write_bytes(b"x")
    path = "001 - Song/001 - Song.opus"
    response, content = request(port, "POST", "/api/set-result", {"path": path, "what": "key", "value": "Fa#m"})
    assert response.status == 200 and json.loads(content)["text"].startswith("F#m")
    response, content = request(port, "POST", "/api/set-result", {"path": path, "what": "bpm", "value": "98.5"})
    assert json.loads(content) == {"text": f"98.5 BPM  {results.HAND}", "note": None}
    (song,) = get_json(port, "/api/library")["folders"][0]["songs"]
    assert song["key"].startswith("F#m") and song["bpm"] == f"98.5 BPM  {results.HAND}"
    # Over a practice click: the click follows the new tempo.
    results.save(root / path, "tempo", "98.50 BPM 4/4, first beat 0.500 s")
    content = request(port, "POST", "/api/set-result", {"path": path, "what": "bpm", "value": "140"})[1]
    assert json.loads(content)["text"] == f"140.00 BPM 4/4, first beat 0.500 s  {results.HAND}"
    (song,) = get_json(port, "/api/library")["folders"][0]["songs"]
    assert song["click"] == {"bpm": 140, "meter": "4/4", "first": 0.5}
    for bad in [{"what": "key", "value": "H"}, {"what": "bpm", "value": "fast"}, {"what": "click", "value": "1"}, {"what": "key"}]:
        response, content = request(port, "POST", "/api/set-result", {"path": path, **bad})
        assert response.status == 400
    assert "no es una tonalidad" in json.loads(request(port, "POST", "/api/set-result",
                                                       {"path": path, "what": "key", "value": "H"})[1])["error"]
    assert request(port, "POST", "/api/set-result", {"path": "../x.opus", "what": "key", "value": "Am"})[0].status == 403
    assert request(port, "POST", "/api/set-result", {"path": "none.opus", "what": "key", "value": "Am"})[0].status == 404
