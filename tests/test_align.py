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
    song = synth.song(tmp_path, "001 - Song.wav", audio)
    synth.write(song.parent / "drums.wav", audio)  # the song's, not its stems'
    align.run([str(tmp_path)])
    saved = results.read(song, "tempo")
    assert not saved.endswith(results.HAND)
    found = align.grid(song)
    assert found["bpm"] == pytest.approx(110, abs=0.02) and found["first"] == pytest.approx(0.4, abs=0.005)


def test_run_keeps_a_tempo_set_by_hand(tmp_path, capsys):
    audio = np.concatenate([np.zeros(int(0.4 * synth.SR), np.float32), synth.drum_song(110, bars=16)])
    song = synth.song(tmp_path, "001 - Song.wav", audio)
    results.save(song, "tempo", results.hand("111.0 BPM"))  # typed in: where its beats fall is found at that tempo
    align.run([str(song)])
    found = align.grid(song)
    assert found["bpm"] == 111 and results.by_hand(song, "tempo")
    align.run([str(song)])  # now all of it is known: kept
    assert "--force" in capsys.readouterr().out
    align.run([str(song)], force=True)
    assert align.grid(song)["bpm"] == pytest.approx(110, abs=0.02) and not results.by_hand(song, "tempo")


def test_run_by_hand_and_rename_follows(tmp_path):
    (tmp_path / "001 - Song").mkdir()
    (tmp_path / "001 - Song" / "001 - Song.opus").write_bytes(b"x")
    align.run([str(tmp_path / "001 - Song" / "001 - Song.opus")], bpm=92, meter="6/8", first=0.75)
    assert results.read(tmp_path / "001 - Song", "tempo") == "92.00 BPM 6/8, first beat 0.750 s  set by hand"
    rename.run(str(tmp_path / "001 - Song" / "001 - Song.opus"), "Better")
    assert align.grid(tmp_path / "001 - Better") == {"bpm": 92, "meter": "6/8", "first": 0.75}


@pytest.mark.parametrize("args", [dict(bpm=10, first=0), dict(meter="x", bpm=100, first=0)])
def test_run_invalid(tmp_path, args):
    (tmp_path / "a").mkdir()
    (tmp_path / "a" / "a.opus").write_bytes(b"x")
    with pytest.raises(SystemExit):
        align.run([str(tmp_path / "a" / "a.opus")], **args)
