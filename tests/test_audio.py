"""Commands run on synthetic audio. Needs ffmpeg and rubberband, like the real thing."""

import os

import numpy as np
import pytest
import soundfile as sf

import synth
from song_wizard import audio, bpm, click, convert, key, speed, transpose


def click_onsets(track, threshold=1e-3, gap=0.02):
    """Sample index of the start of each click, and its peak in the first 2 ms."""
    loud = np.flatnonzero(np.abs(track) > threshold)
    starts = loud[np.insert(np.diff(loud) > gap * click.SR, 0, True)]
    peaks = [np.abs(track[s:s + int(0.002 * click.SR)]).max() for s in starts]
    return starts, np.array(peaks)


def read_click(folder):
    (name,) = os.listdir(folder)
    track, sr = sf.read(folder / name, dtype="float32")
    assert sr == click.SR
    return name, track


@pytest.mark.parametrize("tempo", [120, 123.7, 67.3])
def test_click_is_exact_for_ten_minutes(tmp_path, tempo):
    click.run(tempo, duration="10:00", output=str(tmp_path))
    name, track = read_click(tmp_path)
    assert name == f"Click {tempo:g} BPM 4-4.wav"
    starts, _ = click_onsets(track)
    beats = len(starts)
    assert beats % 4 == 0 and (beats - 4) * 60 / tempo < 600 <= beats * 60 / tempo
    expected = np.arange(beats) * 60 / tempo
    # The tone starts at sin(0) = 0, so the first audible sample is one after the click's start.
    error = np.abs((starts - 1) / click.SR - expected)
    assert error.max() < 0.0001


def test_click_accents_and_subdivisions(tmp_path):
    click.run(100, meter="3/4", bars=4, subdivide=2, output=str(tmp_path))
    name, track = read_click(tmp_path)
    assert name == "Click 100 BPM 3-4 x2.wav"
    starts, peaks = click_onsets(track)
    assert len(starts) == 4 * 3 * 2
    kinds = ["accent" if p > 0.6 else "beat" if p > 0.35 else "sub" for p in peaks]
    assert kinds[:6] == ["accent", "sub", "beat", "sub", "beat", "sub"]
    assert kinds == kinds[:6] * 4
    assert np.abs((starts - 1) / click.SR - np.arange(24) * 0.3).max() < 0.0001


def test_click_rounds_up_to_whole_bars(tmp_path):
    click.run(120, duration="0:05", output=str(tmp_path))  # 2.5 bars -> 3
    _, track = read_click(tmp_path)
    assert len(click_onsets(track)[0]) == 12


def test_click_like_a_song(tmp_path):
    song = synth.write(tmp_path / "song.wav", synth.sine(440, 9))
    out = tmp_path / "out"
    out.mkdir()
    click.run(60, like=str(song), output=str(out))  # 9 s at 60 BPM in 4/4 -> 3 bars
    _, track = read_click(out)
    assert len(click_onsets(track)[0]) == 12


def test_click_named_after_its_song(tmp_path):
    show = tmp_path / "Show"
    show.mkdir()
    song = synth.write(show / "001 - Song (80%).wav", synth.sine(440, 3))
    click.run(96, like=str(song))  # --like names it after the song and saves it next to it
    click.run(96, bars=2, subdivide=2, song=str(song))
    assert sorted(os.listdir(show)) == ["001 - Song (80%) (click 96 BPM 4-4 x2).wav",
                                       "001 - Song (80%) (click 96 BPM 4-4).wav", "001 - Song (80%).wav"]
    assert all(audio.base_of(n) == "001 - Song" for n in os.listdir(show))
    out = tmp_path / "out"
    out.mkdir()
    click.run(96, song=str(song), output=str(out))  # -o still decides where
    assert os.listdir(out) == ["001 - Song (80%) (click 96 BPM 4-4).wav"]


@pytest.mark.parametrize("args", [dict(bpm=10), dict(bpm=500), dict(bpm=120, subdivide=9), dict(bpm=120, bars=0)])
def test_click_invalid(tmp_path, args):
    with pytest.raises(SystemExit):
        click.run(output=str(tmp_path), **args)


def transposed(src, semitones):
    transpose.run(semitones, [str(src)])
    out = audio.output_path(str(src), f"{semitones:+g}")
    data, sr = sf.read(out, dtype="float32", always_2d=True)
    assert sr == synth.SR
    return data.T


def test_transpose_zero_is_the_original(tmp_path):
    original = synth.sine(440, 3, peak=1.5)
    src = synth.write(tmp_path / "tone.wav", original)
    shifted = transposed(src, 0)
    assert shifted.shape == original.shape
    # Only the abrupt start of the sine is smoothed; from there on it's the same audio, no delay.
    start = int(0.05 * synth.SR)
    assert np.abs(shifted[:, start:] - original[:, start:]).max() < 1e-4


@pytest.mark.parametrize("semitones, freq", [(12, 880), (-2, 392), (1, 466.2)])
def test_transpose_changes_pitch_keeps_length_and_peaks(tmp_path, semitones, freq):
    original = synth.sine(440, 3, peak=1.5)
    src = synth.write(tmp_path / "tone.wav", original)
    shifted = transposed(src, semitones)
    assert shifted.shape == original.shape
    assert synth.dominant_freq(shifted[0]) == pytest.approx(freq, abs=1)
    # Peaks above 0 dB survive (rubberband alone would clip them at 1.0).
    assert np.abs(shifted).max() == pytest.approx(1.5, rel=0.02)


def sped(src, percent, semitones=0):
    speed.run(percent, [str(src)], semitones=semitones)
    label = f"{percent:g}%" + (f", {semitones:+g}" if semitones else "")
    data, sr = sf.read(audio.output_path(str(src), label), dtype="float32", always_2d=True)
    assert sr == synth.SR
    return data.T


@pytest.mark.parametrize("percent", [25, 50, 80, 87.5, 150, 200])
def test_speed_keeps_pitch_and_peaks(tmp_path, percent):
    original = synth.sine(440, 4, peak=1.5)
    src = synth.write(tmp_path / "tone.wav", original)
    out = sped(src, percent)
    assert out.shape == (2, round(original.shape[1] * 100 / percent))
    assert synth.dominant_freq(out[0]) == pytest.approx(440, abs=1)
    middle = out[:, out.shape[1] // 4:-out.shape[1] // 4]
    assert np.abs(middle).max() == pytest.approx(1.5, rel=0.02)


def test_speed_and_semitones(tmp_path):
    src = synth.write(tmp_path / "tone.wav", synth.sine(440, 4))
    out = sped(src, 80, semitones=-2)
    assert out.shape[1] == 5 * synth.SR
    assert synth.dominant_freq(out[0]) == pytest.approx(392, abs=1)


@pytest.mark.parametrize("percent", [75, 125])
def test_speed_moves_beats_to_the_new_tempo(tmp_path, percent):
    click.run(120, bars=8, output=str(tmp_path))
    (name,) = os.listdir(tmp_path)
    out = sped(tmp_path / name, percent)
    starts, _ = click_onsets(out[0], threshold=0.02)
    expected = np.arange(32) * 0.5 * 100 / percent
    assert len(starts) == 32
    # A slowed-down attack spreads a little (up to ~4 ms at 75%), but never drifts.
    assert np.abs(starts / synth.SR - expected).max() < 0.006


@pytest.mark.parametrize("percent", [10, 24, 201])
def test_speed_out_of_range(tmp_path, percent):
    src = synth.write(tmp_path / "tone.wav", synth.sine(440, 1))
    with pytest.raises(SystemExit):
        speed.run(percent, [str(src)])


def test_unreadable_file_is_skipped(tmp_path, capsys):
    (tmp_path / "broken.wav").write_bytes(b"not audio")
    good = synth.write(tmp_path / "good.wav", synth.sine(440, 1))
    transpose.run(1, [str(tmp_path / "broken.wav"), str(good)])
    assert "could not read" in capsys.readouterr().out
    assert sorted(os.listdir(tmp_path)) == ["broken.wav", "good (+1).wav", "good.wav"]


@pytest.mark.parametrize("k, minor", [("G", False), ("A", True), ("Eb", False), ("F#", True)])
def test_key(tmp_path, k, minor, capsys):
    name = f"{k}{'m' if minor else ''}.wav"
    synth.write(tmp_path / name, synth.chord_song(k, minor))
    key.run([str(tmp_path)])
    assert capsys.readouterr().out.split()[0] == name[:-4]
    line = (tmp_path / "key.txt").read_text().splitlines()[1]
    assert line.startswith(f"{name}\t{name[:-4]} ")
    assert line.endswith("4/4")


@pytest.mark.parametrize("tempo", [90, 120, 137])
def test_bpm(tmp_path, tempo):
    mono = synth.drum_song(tempo)
    found, _, low, high, confidence = bpm.analyze(mono)
    assert found == pytest.approx(tempo, abs=0.5)
    assert bpm.describe(found, low, high, confidence) == ("steady", True)


def test_bpm_saves_results(tmp_path):
    synth.write(tmp_path / "beat.wav", synth.drum_song(120, bars=16))
    bpm.run([str(tmp_path)])
    name, result = (tmp_path / "bpm.txt").read_text().splitlines()[1].split("\t")
    assert name == "beat.wav" and result.endswith("BPM  steady")


def peak_db(path):
    data, _ = audio.load(str(path))
    return 20 * np.log10(np.abs(data).max())


def test_convert_turns_down_only_loud_files(tmp_path):
    synth.write(tmp_path / "loud.wav", synth.sine(440, 5, peak=1.5))
    synth.write(tmp_path / "quiet.wav", synth.sine(440, 5, peak=0.5))
    convert.run([str(tmp_path)])
    # Encoding adds a hair to the peaks: what matters is that it stays clear of 0 dB.
    assert -1.5 < peak_db(tmp_path / "loud.mp3") < -0.5
    assert peak_db(tmp_path / "quiet.mp3") == pytest.approx(20 * np.log10(0.5), abs=0.3)


def test_convert_m4a(tmp_path):
    src = synth.write(tmp_path / "song.wav", synth.sine(440, 3))
    convert.run([str(src)], fmt="m4a")
    assert peak_db(tmp_path / "song.m4a") < 0


def test_convert_folder_skips_lossy(tmp_path):
    synth.write(tmp_path / "a.wav", synth.sine(440, 1))
    (tmp_path / "b.opus").write_bytes(b"not really opus")
    (tmp_path / "c.mp3").write_bytes(b"not really mp3")
    convert.run([str(tmp_path)])
    assert sorted(os.listdir(tmp_path)) == ["a.mp3", "a.wav", "b.opus", "c.mp3"]
    assert (tmp_path / "c.mp3").read_bytes() == b"not really mp3"


def test_convert_does_not_overwrite(tmp_path):
    src = synth.write(tmp_path / "a.wav", synth.sine(440, 1))
    (tmp_path / "a.mp3").write_bytes(b"keep me")
    convert.run([str(src)])
    assert (tmp_path / "a.mp3").read_bytes() == b"keep me"
    convert.run([str(src)], overwrite=True)
    assert (tmp_path / "a.mp3").read_bytes() != b"keep me"
    assert peak_db(tmp_path / "a.mp3") < 0


@pytest.mark.slow
def test_separate_adds_up_to_the_original(tmp_path):
    from song_wizard import separate
    drums = synth.drum_song(110, bars=4)
    mix = drums + synth.sine(330, len(drums) / synth.SR, peak=0.3, channels=1)[0]
    src = synth.write(tmp_path / "song.wav", np.tile(mix, (2, 1)) * 2)  # peaks above 0 dB too
    separate.run(["drums"], [str(src)])
    original, _ = sf.read(src, dtype="float32", always_2d=True)
    drums, _ = sf.read(tmp_path / "song (drums).wav", dtype="float32", always_2d=True)
    rest, _ = sf.read(tmp_path / "song (no drums).wav", dtype="float32", always_2d=True)
    assert np.abs(drums + rest - original).max() < 1e-5
    # The drums go to the drum stem: the rest is mostly the sine.
    assert synth.dominant_freq(rest[:, 0]) == pytest.approx(330, abs=2)
