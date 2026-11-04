"""Chords: BTC's labels written as on a chord sheet, moved onto the click's beats, what was corrected
by hand kept, the file checked and saved (any name allowed, its text escaped), going along with the
song when it's renamed or trimmed, and the model used only if its SHA-256 matches. Detecting with
the real model needs to download it: "uv run pytest -m network"."""

import hashlib
import io
import json
import time

import pytest

import synth
from test_ui import get_json, request, server  # noqa: F401  (the fixture)

from song_wizard import align, chords, rename, results, trim, ui

CLICK = {"bpm": 120.0, "meter": "4/4", "first": 0.5}  # a beat every 0.5 s


def test_pretty():
    assert [chords.pretty(x) for x in ["A", "A:min7", "C#:hdim7", "Bb:sus4", "N", "X"]] == \
        ["A", "Am7", "C#m7b5", "Bbsus4", "N.C.", "N.C."]


def test_understood():
    for name in ["A", "Am", "F#m7", "Bbmaj7", "Asus4", "C/E", "Dm7b5", "G7", "N.C.", "Cadd9"]:
        assert chords.understood(name), name
    for name in ["Riff", "ver tab", "H7", "a"]:
        assert not chords.understood(name), name


def test_on_beats():
    found = [(0.0, 0.62, "N"), (0.62, 2.43, "A"), (2.43, 2.6, "E"), (2.6, 4.55, "A:min"), (4.55, 6.0, "A:min")]
    out = chords.on_beats(found, CLICK, 6.0)
    # Changes land on beats (0.5, 2.5, 4.5...); the flicker of E (under half a beat) is gone and the
    # chord before lasts until the next; two pieces of the same chord become one.
    assert [(c["from"], c["to"], c["name"]) for c in out] == [(0.0, 0.5, "N.C."), (0.5, 2.5, "A"), (2.5, 6.0, "Am")]


def test_keep_hand():
    new = [{"from": 0.5, "to": 2.5, "name": "A", "hand": False}, {"from": 2.5, "to": 4.5, "name": "E", "hand": False}]
    old = {"chords": [{"from": 1.5, "to": 3.5, "name": "Riff", "hand": True}]}
    out = chords.keep_hand(new, old)
    assert [(c["from"], c["to"], c["name"], c["hand"]) for c in out] == \
        [(0.5, 1.5, "A", False), (1.5, 3.5, "Riff", True), (3.5, 4.5, "E", False)]


def test_save_any_name_escaped(tmp_path):
    song = tmp_path / "001 - Band - Song.opus"
    song.write_bytes(b"x")
    data = chords.save(song, {"chords": [{"from": 0, "to": 2, "name": 'A "riff" \\ <b>', "hand": True}], "click": CLICK})
    raw = (tmp_path / "001 - Band - Song.chords.json").read_text(encoding="utf-8")
    assert json.loads(raw)["chords"][0]["name"] == 'A "riff" \\ <b>' and data == chords.load(song)


@pytest.mark.parametrize("bad", [
    {"chords": "A"},
    {"chords": [{"from": 2, "to": 1, "name": "A"}]},
    {"chords": [{"from": 0, "to": 1, "name": "  "}]},
    {"chords": [{"from": 0, "to": 2, "name": "A"}, {"from": 1, "to": 3, "name": "E"}]},
    {"chords": [{"from": -1, "to": 2, "name": "A"}]},
])
def test_clean_rejects(bad):
    with pytest.raises((ValueError, KeyError, TypeError)):
        chords.clean(bad)


def test_long_name_cut(tmp_path):
    song = tmp_path / "s.opus"
    song.write_bytes(b"x")
    assert chords.save(song, {"chords": [{"from": 0, "to": 1, "name": "x" * 100}]})["chords"][0]["name"] == "x" * 24


def test_goes_along_with_rename(tmp_path):
    folder = tmp_path / "Show"
    folder.mkdir()
    song = folder / "001 - Band - Song.opus"
    synth.write(song.with_suffix(".wav"), synth.sine(440, 1.0))
    song.with_suffix(".wav").rename(song)
    chords.save(song, {"chords": [{"from": 0, "to": 1, "name": "A"}]})
    rename.run(str(song), "Band - Other")
    assert (folder / "001 - Band - Other.chords.json").is_file()
    assert not (folder / "001 - Band - Song.chords.json").exists()


def test_follows_trim(tmp_path):
    folder = tmp_path / "Show"
    folder.mkdir()
    song = folder / "001 - Song.wav"
    synth.write(song, synth.sine(440, 10.0))
    results.save("click", [(str(song), align.describe(120, "4/4", 0.25))])
    chords.save(song, {"chords": [{"from": 0.25, "to": 3.0, "name": "A"}, {"from": 3.0, "to": 9.5, "name": "E", "hand": True}],
                       "click": {"bpm": 120, "meter": "4/4", "first": 0.25}})
    trim.run(str(song), start="2", end="8", yes=True)
    data = chords.load(song)
    # 2 s cut off the start and the end at 8: A keeps its last second, E is clipped to the new end.
    assert [(c["from"], c["to"], c["name"], c["hand"]) for c in data["chords"]] == \
        [(0.0, 1.0, "A", False), (1.0, 6.0, "E", True)]
    assert data["click"]["first"] == pytest.approx(0.25)


class Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()


def test_model_only_if_its_hash_matches(tmp_path, monkeypatch):
    monkeypatch.setattr(chords, "MODELS_DIR", tmp_path)
    monkeypatch.setattr(chords.urllib.request, "urlopen", lambda *a, **k: Response(b"something else"))
    with pytest.raises(SystemExit, match="SHA-256"):
        chords.model_path()
    assert not any(tmp_path.iterdir())  # nothing kept
    good = b"the real weights"
    monkeypatch.setattr(chords, "MODEL_SHA256", hashlib.sha256(good).hexdigest())
    monkeypatch.setattr(chords.urllib.request, "urlopen", lambda *a, **k: Response(good))
    path = chords.model_path()
    assert path.read_bytes() == good
    # Already there and right: not downloaded again.
    monkeypatch.setattr(chords.urllib.request, "urlopen", lambda *a, **k: pytest.fail("downloaded again"))
    assert chords.model_path() == path


@pytest.mark.network
def test_detects_a_progression(tmp_path):
    """The real model on a synthetic I-IV-V-I in G: G, C and D come out, on the bars."""
    song = tmp_path / "001 - Song.wav"
    synth.write(song, synth.chord_song("G", bars=16, bpm=100))
    found = chords.detect(str(song), {"bpm": 100.0, "meter": "4/4", "first": 0.0})
    roots = {c["name"].rstrip("m") for c in found if c["name"] != "N.C." and c["to"] - c["from"] >= 2.4}
    assert {"G", "C", "D"} <= roots


def test_interface(server, monkeypatch):  # noqa: F811
    port, root = server
    ran = []
    monkeypatch.setattr(ui.Runner, "run", lambda self, job: ran.append(job.args) or setattr(job, "status", "done"))
    synth.write(root / "001 - Band - Song.wav", synth.sine(440, 5.0))
    path = "001 - Band - Song.wav"
    q = path.replace(" ", "%20")
    assert get_json(port, f"/api/chords?path={q}")["chords"] is None
    assert get_json(port, "/api/library")["folders"][0]["songs"][0]["chords"] is None
    data = {"chords": [{"from": 0, "to": 2, "name": "Am", "hand": True}, {"from": 2, "to": 4, "name": "ver tab"}]}
    assert request(port, "POST", "/api/chords", {"path": path, "chords": data})[0].status == 200
    assert [c["name"] for c in get_json(port, f"/api/chords?path={q}")["chords"]["chords"]] == ["Am", "ver tab"]
    assert get_json(port, "/api/library")["folders"][0]["songs"][0]["chords"]  # changed: the page reloads them
    bad = {"chords": [{"from": 3, "to": 1, "name": "A"}]}
    assert request(port, "POST", "/api/chords", {"path": path, "chords": bad})[0].status == 400
    assert request(port, "POST", "/api/chords", {"path": "../x.wav", "chords": data})[0].status == 403
    assert request(port, "POST", "/api/jobs", {"action": "chords", "paths": [path]})[0].status == 200
    for _ in range(50):
        if ran:
            break
        time.sleep(0.05)
    assert ran and ran[0][0] == "chords" and ran[0][-1].endswith(path)
