"""Drums: the hits found in the model's activations (faked here: the model has its own license and
is downloaded only after asking), the ride told from the crash and the open hi-hat from the closed
one by the drum kit stems, the file checked and saved, the model asked for before downloading,
the sheet (bars on the click's grid, repeated bars folded), MIDI, going along with the song, and
the page. The real model runs on a synthetic beat with "uv run pytest -m network"."""

import json
import urllib.parse

import numpy as np
import pytest

import synth
from test_ui import get_json, request, server  # noqa: F401  (the fixture)

from song_wizard import drums, drumsheet, rename, results, trim, ui

# 120 BPM in 4/4 from 0: a beat is 0.5 s, a sixteenth 0.125 s, a bar 2 s.
CLICK = {"bpm": 120.0, "meter": "4/4", "first": 0.0}


def beat(bars=4):
    """Kick on 1 and 3, snare on 2 and 4, closed hi-hat on eighths: as hits."""
    hits = []
    for k in range(bars * 4):
        hits.append({"t": k * 0.5, "part": "kick" if k % 2 == 0 else "snare"})
        hits += [{"t": k * 0.5, "part": "hihat"}, {"t": k * 0.5 + 0.25, "part": "hihat"}]
    return hits


def test_peaks():
    a = np.zeros(300)
    for i, v in [(50, 0.9), (52, 0.5), (100, 0.3), (150, 0.1), (200, 0.8), (202, 0.85)]:
        a[i] = v
    # 52 is next to a higher one, 150 is under the threshold, 200 and 202 are one hit (the first).
    assert drums.peaks(a, 0.22).tolist() == [0.5, 1.0, 2.0]


def test_offset():
    times = np.arange(40) * 0.125 + 0.018
    assert drums.offset(times, CLICK) == pytest.approx(0.018)
    assert drums.offset(times[:5], CLICK) == 0.0  # too few to tell
    assert drums.offset(np.arange(40) * 0.125 + 0.06, CLICK) == pytest.approx(0.04)  # never more than 40 ms


def burst(at, decay, seconds=4.0, seed=0):
    """Noise bursts at those times, decaying at that rate."""
    rng = np.random.default_rng(seed)
    out = np.zeros(int(seconds * synth.SR))
    t = np.arange(int(0.6 * synth.SR)) / synth.SR
    for a in at:
        i = int(a * synth.SR)
        out[i:i + len(t)] += (rng.standard_normal(len(t)) * np.exp(-t * decay))[:len(out) - i]
    return (0.5 * out / np.abs(out).max()).astype(np.float32)


def test_cymbals_and_hihats(tmp_path):
    ride = drums.envelope(synth.write(tmp_path / "ride.wav", burst([0.5, 1.5], 10)))
    crash = drums.envelope(synth.write(tmp_path / "crash.wav", burst([1.0, 2.5], 4)))
    assert drums.cymbals([0.5, 1.0, 1.5, 2.5], ride, crash) == ["ride", "crash", "ride", "crash"]
    assert drums.cymbals([0.5], None, crash) == ["crash"]
    # A short hit, a ringing one, a short one.
    hat = np.concatenate([burst([0.5], 80, 1.0), burst([0.5], 3, 1.0, seed=1), burst([0.5], 80, 1.0, seed=2)])
    env = drums.envelope(synth.write(tmp_path / "hat.wav", hat))
    assert drums.hihats([0.5, 1.5, 2.5], env) == ["hihat", "hhopen", "hihat"]
    assert drums.hihats([0.5], None) == ["hihat"]


@pytest.fixture
def song(tmp_path):
    folder = tmp_path / "Show"
    folder.mkdir()
    path = folder / "001 - Band - Song.wav"
    synth.write(path, synth.sine(440, 4.0))
    return path


def fake_model(monkeypatch, frames=400):
    """The model, faked: a kick at 0.5 s and 1.52 s (20 ms late), a snare at 1.0 s, a cymbal at 2.0 s, a hi-hat at 3.0 s."""
    act = np.zeros((frames, 5), dtype=np.float32)
    for frame, k in [(50, 0), (152, 0), (100, 1), (200, 4), (300, 3)]:
        act[frame, k] = 0.9
    monkeypatch.setattr(drums, "activations", lambda audio: act)
    monkeypatch.setattr(drums, "model_ready", lambda: True)


def test_detect(song, monkeypatch):
    fake_model(monkeypatch)
    hits = drums.detect(song, CLICK)
    # Too few to measure a delay; without the kit's stems a cymbal is a crash and the hi-hat closed.
    assert [(h["t"], h["part"]) for h in hits] == [(0.5, "kick"), (1.0, "snare"), (1.52, "kick"), (2.0, "crash"), (3.0, "hihat")]
    synth.write(song.with_name("001 - Band - Song (ride).wav"), burst([2.0], 10))
    synth.write(song.with_name("001 - Band - Song (crash).wav"), burst([3.5], 10))
    synth.write(song.with_name("001 - Band - Song (hihat).wav"), burst([3.0], 3))
    assert [h["part"] for h in drums.detect(song, CLICK)][3:] == ["ride", "hhopen"]


@pytest.mark.parametrize("bad", [
    {"hits": [{"t": 1, "part": "cowbell"}]},
    {"hits": [{"t": -1, "part": "kick"}]},
    {"hits": "nope"},
    {"notes": []},
])
def test_clean_rejects(bad):
    with pytest.raises((ValueError, KeyError, TypeError)):
        drums.clean(bad)


def test_keep_hand():
    new = [{"t": 1.0, "part": "kick", "hand": False}, {"t": 2.0, "part": "snare", "hand": False}]
    old = {"hits": [{"t": 1.02, "part": "kick", "hand": True}, {"t": 3.0, "part": "crash", "hand": True}]}
    assert [(h["t"], h["part"], h["hand"]) for h in drums.keep_hand(new, old)] == \
        [(1.02, "kick", True), (2.0, "snare", False), (3.0, "crash", True)]


def test_run_asks_for_the_model_first(song, monkeypatch, capsys):
    results.save("click", [(str(song), "120.00 BPM 4/4, first beat 0.000 s")])
    monkeypatch.setattr(drums, "model_ready", lambda: False)
    monkeypatch.setattr(drums, "model_path", lambda: pytest.fail("downloaded without asking"))
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    drums.run([str(song)])
    out = capsys.readouterr().out
    assert "CC BY-NC-SA 4.0" in out and "--accept-model-license" in out and not drums.path_for(song).exists()


def test_run_keeps_hand_and_exports(song, monkeypatch, capsys):
    results.save("click", [(str(song), "120.00 BPM 4/4, first beat 0.000 s")])
    for part in drums.KIT:  # the kit's stems are there: nothing to separate
        synth.write(song.with_name(f"001 - Band - Song ({part}).wav"), burst([3.9], 50))
    fake_model(monkeypatch)
    drums.run([str(song)])
    data = drums.load(song)
    assert data["click"] == CLICK and "ADTOF" in data["source"] and len(data["hits"]) == 5
    data["hits"].append({"t": 3.5, "part": "toms", "hand": True})
    drums.save(song, data)
    drums.run([str(song)])
    assert any(h["part"] == "toms" for h in drums.load(song)["hits"])
    drums.run([str(song)], force=True)
    assert not any(h["part"] == "toms" for h in drums.load(song)["hits"])
    drums.run([str(song)], sheet=True, as_midi=True)
    assert song.with_name("001 - Band - Song.drums.html").is_file() and song.with_name("001 - Band - Song.drums.mid").is_file()


def test_midi():
    data = {"hits": beat(1) + [{"t": 0.0, "part": "crash"}], "click": CLICK}
    raw = drums.midi(data)
    assert raw[:4] == b"MThd" and raw[14:18] == b"MTrk"
    assert raw.count(bytes([0x99, 36, 100])) == 2 and raw.count(bytes([0x99, 38, 100])) == 2
    assert raw.count(bytes([0x99, 42, 100])) == 8 and raw.count(bytes([0x99, 49, 100])) == 1
    assert b"\xff\x51\x03" + (500000).to_bytes(3, "big") in raw  # 120 BPM


def test_grid_and_folding():
    data = {"hits": beat(4) + [{"t": 8.25, "part": "crash"}], "click": CLICK}
    bars, per_bar = drumsheet.grid(data)
    assert per_bar == 16 and sorted(bars) == [0, 1, 2, 3, 4]
    assert (0, "kick") in bars[0] and (4, "snare") in bars[0] and (2, "hihat") in bars[0]
    # Bars 2-4 like bar 1: one sign with ×3; then the crash, in bar 5.
    assert [(kind, n) for kind, n, _ in drumsheet.items(bars)] == [("bar", 0), ("repeat", 1), ("bar", 4)]
    assert drumsheet.items(bars)[1][2] == 3
    assert [kind for kind, *_ in drumsheet.items(bars, fold=False)] == ["bar"] * 5
    # Bars without hits: one rest that says how many.
    data = {"hits": beat(1) + [{"t": 10.0, "part": "kick"}], "click": CLICK}
    assert [(k, n, w if k != "bar" else None) for k, n, w in drumsheet.items(drumsheet.grid(data)[0])] == \
        [("bar", 0, None), ("rest", 1, 4), ("bar", 5, None)]


def test_open_hihat_wins_and_meter():
    data = {"hits": [{"t": 0.0, "part": "hihat"}, {"t": 0.01, "part": "hhopen"}], "click": {**CLICK, "meter": "3/4"}}
    bars, per_bar = drumsheet.grid(data)
    assert per_bar == 12 and bars[0] == frozenset({(0, "hhopen")})
    assert drumsheet.meter({"meter": "6/8"}) == (3, 6, 8) and drumsheet.meter({"meter": "x"}) == (4, 4, 4)


def test_sheet():
    data = {"hits": beat(4), "click": CLICK}
    xml = drumsheet.musicxml("A & B", data)
    assert 'measure-repeat type="start"' in xml and "×3" in xml and "A &amp; B" in xml and "<per-minute>120" in xml
    assert '<beam number="1">begin</beam>' in xml and "<notehead>x</notehead>" in xml
    pages = drumsheet.render(xml)
    assert len(pages) == 1 and "mRpt" in pages[0]
    page = drumsheet.page("Song", data, "en", hidden=[("path", "Show/a.wav"), ("lang", "en")])
    assert 'class="wm"' in page and 'name="fold" value="1" checked' in page and "/drums.mid?path=Show/a.wav" in page
    assert "ADTOF" in page and "<svg" in page
    assert '<form class="bar"' not in drumsheet.page("Song", data, "en")  # saved to a file: no choices
    # The browser offers the title as the PDF's name; no page margins, so it adds no date or address.
    page = drumsheet.page("Song", data, "en", artist="Band")
    assert "<title>Band - Song - drum tab by song-wizard</title>" in page and "margin: 0;" in page
    assert '<div class="artist">Band</div>' in page and "1 / 1" in page and "data:image/png;base64," in page
    assert 'viewBox="0 0 ' in page and 'preserveAspectRatio="xMidYMin meet"' in page


def test_first_page_shorter_same_size():
    """The first page leaves room for the heading with fewer systems, not smaller ones: the rest
    start at the next bar, and no bar is lost or repeated."""
    import re
    xml = drumsheet.musicxml("Song", {"hits": beat(160), "click": CLICK}, fold=False)
    whole = drumsheet.render(xml)
    split = drumsheet.render(xml, first_height=1500)
    count = lambda pages: [len(re.findall(r'class="measure"', p)) for p in pages]
    assert sum(count(split)) == sum(count(whole)) == 160
    assert not any("<title" in p for p in split)
    assert count(split)[0] < count(whole)[0] and len(split) >= len(whole)
    size = lambda svg: tuple(map(float, re.match(r'<svg viewBox="0 0 ([\d.]+) ([\d.]+)"', svg).groups()))
    assert size(split[0])[0] == size(split[1])[0] and size(split[0])[1] < size(split[1])[1]
    assert drumsheet.file_title("A/B: C?", "X") == "X - A-B- C- - drum tab by song-wizard"
    assert drumsheet.file_title("Song", "Ann & Bob") == "Ann and Bob - Song - drum tab by song-wizard"
    page = drumsheet.page("Song", {"hits": beat(1), "click": CLICK}, "en", artist="Ann & Bob")
    assert "<title>Ann and Bob - Song" in page and '<div class="artist">Ann &amp; Bob</div>' in page


def test_goes_along(song):
    drums.save(song, {"hits": [{"t": 0.5, "part": "kick"}, {"t": 3.0, "part": "snare"}], "click": {**CLICK, "first": 0.25}})
    trim.run(str(song), start="1", yes=True)
    data = drums.load(song)
    assert [(h["t"], h["part"]) for h in data["hits"]] == [(2.0, "snare")] and data["click"]["first"] == 0.25
    rename.run(str(song), "Band - Other")
    assert song.with_name("001 - Band - Other.drums.json").is_file()


def test_interface(server, monkeypatch):  # noqa: F811
    port, root = server
    ran = []
    monkeypatch.setattr(ui.Runner, "run", lambda self, job: ran.append(job.args) or setattr(job, "status", "done"))
    monkeypatch.setattr(drums, "model_ready", lambda: False)
    synth.write(root / "001 - Song.wav", synth.sine(440, 3.0))
    q = urllib.parse.quote("001 - Song.wav")
    assert get_json(port, f"/api/drums?path={q}")["drums"] is None
    assert request(port, "GET", f"/drums?path={q}")[0].status == 404
    # The model isn't here: the page is asked to agree first; then it's passed on.
    response, content = request(port, "POST", "/api/jobs", {"action": "drums", "paths": ["001 - Song.wav"]})
    assert response.status == 409 and json.loads(content)["consent"] == "drums" and not ran
    response, content = request(port, "POST", "/api/jobs", {"action": "drums", "paths": ["001 - Song.wav"], "accept": True})
    assert response.status == 200
    for _ in range(50):
        if ran:
            break
        __import__("time").sleep(0.05)
    assert ran and ran[0][:2] == ["drums", "--accept-model-license"]
    drums.save(root / "001 - Song.wav", {"hits": beat(2), "click": CLICK})
    assert get_json(port, "/api/library")["folders"][0]["songs"][0]["drums"]
    response, content = request(port, "GET", f"/drums?path={q}&fold=0")
    assert response.status == 200 and b"<svg" in content and b'value="1" onchange' in content
    response, content = request(port, "GET", f"/drums.mid?path={q}")
    assert response.status == 200 and content.startswith(b"MThd")
    assert "001%20-%20Song.drums.mid" in response.getheader("Content-Disposition")


@pytest.mark.network
def test_real_model(tmp_path):
    """ADTOF on a synthetic rock beat: kicks on 1 and 3, snares on 2 and 4."""
    song = synth.write(tmp_path / "001 - Beat.wav", synth.drum_song(bpm=120, bars=8))
    hits = drums.detect(song, CLICK)
    on = lambda part: [round(h["t"] / 0.5) % 4 for h in hits if h["part"] == part]
    kicks, snares = on("kick"), on("snare")
    assert len(kicks) > 10 and len(snares) > 10
    assert sum(k in (0, 2) for k in kicks) / len(kicks) > 0.9
    assert sum(s in (1, 3) for s in snares) / len(snares) > 0.9
