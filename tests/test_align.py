"""align: the exact tempo and first beat, for the practice player's click."""

import numpy as np
import pytest

import synth
from song_wizard import align, rename, results


@pytest.mark.parametrize("tempo, intro", [(120, 0), (120, 0.73), (97.3, 1.25), (137, 0.31)])
def test_detect(tempo, intro):
    audio = np.concatenate([np.zeros(int(intro * synth.SR), np.float32), synth.drum_song(tempo, bars=24)])
    bpm, first, steady = align.detect(audio)
    assert bpm == pytest.approx(tempo, abs=0.02)
    assert first == pytest.approx(intro, abs=0.005)
    assert steady


def test_describe_and_parse():
    text = align.describe(97.3, "3/4", 1.25)
    assert text == "97.30 BPM 3/4, first beat 1.250 s"
    assert align.parse(text) == {"bpm": 97.3, "meter": "3/4", "first": 1.25}
    assert align.parse("98.0 BPM  steady") is None and align.parse(None) is None


def test_run_detects_and_saves(tmp_path, capsys):
    audio = np.concatenate([np.zeros(int(0.4 * synth.SR), np.float32), synth.drum_song(110, bars=16)])
    synth.write(tmp_path / "001 - Song.wav", audio)
    synth.write(tmp_path / "001 - Song (drums).wav", audio)  # stems are skipped in folders
    align.run([str(tmp_path)])
    saved = results.read(str(tmp_path), "click")
    assert list(saved) == ["001 - Song.wav"]
    found = align.parse(saved["001 - Song.wav"])
    assert found["bpm"] == pytest.approx(110, abs=0.02) and found["first"] == pytest.approx(0.4, abs=0.005)


def test_run_by_hand_and_rename_follows(tmp_path):
    (tmp_path / "001 - Song.opus").write_bytes(b"x")
    align.run([str(tmp_path / "001 - Song.opus")], bpm=92, meter="6/8", first=0.75)
    assert results.read(str(tmp_path), "click") == {"001 - Song.opus": "92.00 BPM 6/8, first beat 0.750 s"}
    rename.run(str(tmp_path / "001 - Song.opus"), "Better")
    assert list(results.read(str(tmp_path), "click")) == ["001 - Better.opus"]


@pytest.mark.parametrize("args", [dict(bpm=10, first=0), dict(meter="x", bpm=100, first=0)])
def test_run_invalid(tmp_path, args):
    (tmp_path / "a.opus").write_bytes(b"x")
    with pytest.raises(SystemExit):
        align.run([str(tmp_path / "a.opus")], **args)
