"""Notes: the bass's followed with pYIN on its stem (synthetic here), notes split, joined and kept
in the part's range, the file checked and saved, what was corrected by hand kept, going along with
the song, and the page reading and saving them. The voice's need CREPE's model (89 MB):
"uv run pytest -m network"."""

import json
import time

import numpy as np
import pytest

import synth
from test_ui import get_json, request, server  # noqa: F401  (the fixture)

from song_wizard import notes, rename, trim, ui


def line(midis, each=0.5, sr=synth.SR):
    """A bass line: one plucked note per `each` seconds."""
    out = np.concatenate([synth.tone(m, each) for m in midis])
    return (0.8 * out / np.abs(out).max()).astype(np.float32)


def test_segment():
    t = np.arange(12) * 0.05
    nan = np.nan
    midi = np.array([40, 40, 40, nan, 40, 40, 43, 43, 43, 43, nan, 50.0])
    out = notes.segment(t, midi, 0.05, min_len=0.1, gap=0.06)
    # The same note across a one-frame gap is one note; the lone frame at the end is too short.
    assert [(n["from"], n["to"], n["midi"]) for n in out] == [(0.0, 0.3, 40), (0.3, 0.5, 43)]


def test_bass_line(tmp_path):
    song = tmp_path / "001 - Song.wav"
    synth.write(song, synth.sine(440, 4.0))
    stem = tmp_path / "001 - Song (bass).wav"
    synth.write(stem, line([40, 40, 45, 47, 40, 45, 47, 40]))  # E2 E2 A2 B2...
    assert notes.stem_for(song, "bass") == stem and notes.stem_for(song, "vocals") is None
    found = notes.bass_notes(stem)
    assert [n["midi"] for n in found] == [40, 45, 47, 40, 45, 47, 40]  # the two first E2 joined
    starts = [n["from"] for n in found]
    assert starts[1] == pytest.approx(1.0, abs=0.05) and starts[2] == pytest.approx(1.5, abs=0.05)


def test_run_without_stems(tmp_path, capsys):
    song = tmp_path / "001 - Song.wav"
    synth.write(song, synth.sine(440, 1.0))
    notes.run([str(song)])
    assert "separate it first" in capsys.readouterr().out and not notes.path_for(song).exists()


def test_run_keeps_hand(tmp_path, monkeypatch):
    song = tmp_path / "001 - Song.wav"
    synth.write(song, synth.sine(440, 3.0))
    synth.write(tmp_path / "001 - Song (bass).wav", synth.sine(110, 3.0))
    detected = [{"from": 0.0, "to": 1.0, "midi": 40, "hand": False}, {"from": 1.0, "to": 2.0, "midi": 45, "hand": False}]
    monkeypatch.setitem(notes.DETECT, "bass", (lambda stem: [dict(n) for n in detected], "test"))
    notes.run([str(song)])
    data = notes.load(song)
    data["bass"]["notes"][1] = {"from": 1.0, "to": 2.0, "midi": 46, "hand": True}
    notes.save(song, data)
    notes.run([str(song)])
    assert [n["midi"] for n in notes.load(song)["bass"]["notes"]] == [40, 46]
    notes.run([str(song)], force=True)
    assert [n["midi"] for n in notes.load(song)["bass"]["notes"]] == [40, 45]


@pytest.mark.parametrize("bad", [
    {"guitar": {"notes": []}},
    {"bass": {"notes": [{"from": 2, "to": 1, "midi": 40}]}},
    {"bass": {"notes": [{"from": 0, "to": 1, "midi": 200}]}},
    {"bass": []},
])
def test_clean_rejects(bad):
    with pytest.raises((ValueError, KeyError, TypeError)):
        notes.clean(bad)


def test_goes_along(tmp_path):
    folder = tmp_path / "Show"
    folder.mkdir()
    song = folder / "001 - Band - Song.wav"
    synth.write(song, synth.sine(440, 10.0))
    notes.save(song, {"bass": {"notes": [{"from": 1.0, "to": 3.0, "midi": 40}, {"from": 8.0, "to": 9.5, "midi": 45}]}})
    trim.run(str(song), start="2", end="8", yes=True)
    assert [(n["from"], n["to"]) for n in notes.load(song)["bass"]["notes"]] == [(0.0, 1.0)]
    rename.run(str(song), "Band - Other")
    assert (folder / "001 - Band - Other.notes.json").is_file()


def test_interface(server, monkeypatch):  # noqa: F811
    port, root = server
    ran = []
    monkeypatch.setattr(ui.Runner, "run", lambda self, job: ran.append(job.args) or setattr(job, "status", "done"))
    synth.write(root / "001 - Band - Song.wav", synth.sine(440, 5.0))
    path = "001 - Band - Song.wav"
    q = path.replace(" ", "%20")
    assert get_json(port, f"/api/notes?path={q}")["notes"] is None
    data = {"vocals": {"notes": [{"from": 0, "to": 1, "midi": 64, "hand": True}]}}
    assert request(port, "POST", "/api/notes", {"path": path, "notes": data})[0].status == 200
    assert get_json(port, f"/api/notes?path={q}")["notes"]["vocals"]["notes"][0]["midi"] == 64
    assert get_json(port, "/api/library")["folders"][0]["songs"][0]["notes"]
    assert request(port, "POST", "/api/notes", {"path": path, "notes": {"drums": {"notes": []}}})[0].status == 400
    assert request(port, "POST", "/api/jobs", {"action": "notes", "part": "vocals", "paths": [path]})[0].status == 200
    for _ in range(50):
        if ran:
            break
        time.sleep(0.05)
    assert ran and ran[0][:3] == ["notes", "--part", "vocals"]
    assert request(port, "POST", "/api/jobs", {"action": "notes", "part": "drums", "paths": [path]})[0].status == 400


@pytest.mark.network
def test_voice_melody(tmp_path):
    """CREPE on a synthetic voice (with vibrato): the melody's notes, on time."""
    sr = 16000
    melody = [60, 62, 64, 65, 67, 65, 64, 62]
    y = np.zeros(int(5 * sr))
    for i, m in enumerate(melody):
        n = int(0.4 * sr)
        tt = np.arange(n) / sr
        f = 440 * 2 ** ((m - 69) / 12) * 2 ** (0.3 / 12 * np.sin(2 * np.pi * 5.5 * tt))
        ph = 2 * np.pi * np.cumsum(f) / sr
        s = int((0.5 + 0.5 * i) * sr)
        y[s:s + n] += (np.sin(ph) + 0.5 * np.sin(2 * ph)) * np.minimum(1, tt / 0.02) * 0.3
    stem = tmp_path / "001 - Song (vocals).wav"
    synth.write(stem, y.astype(np.float32), sr=sr)
    found = notes.vocal_notes(stem)
    assert [n["midi"] for n in found] == melody
    assert all(abs(n["from"] - (0.5 + 0.5 * i)) < 0.04 for i, n in enumerate(found))
