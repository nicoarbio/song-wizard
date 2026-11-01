"""Trimming a song with everything made from it: the same cut everywhere (scaled at another speed),
exact to the sample, all or nothing, and the click, lyrics and download link following."""

import json
import os
import subprocess

import numpy as np
import pytest

import synth

from song_wizard import align, lyrics, results, trim

SR = synth.SR


def pulse_song(seconds, at, sr=SR):
    """Silence with a short click at each time in `at`."""
    x = np.zeros((2, int(seconds * sr)), dtype=np.float32)
    for t in at:
        i = int(round(t * sr))
        x[:, i:i + 32] = 0.8
    return x


def decode(path, sr=SR):
    out = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-ac", "1", "-ar", str(sr), "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(out, dtype=np.float32)


def onsets(path, sr=SR):
    x = np.abs(decode(path, sr))
    hits, last = [], -sr
    for i in np.flatnonzero(x > 0.3):
        if i - last > sr // 10:
            hits.append(i / sr)
        last = i
    return hits


@pytest.fixture
def song(tmp_path, monkeypatch):
    folder = tmp_path / "Show"
    folder.mkdir()
    synth.write(folder / "001 - Song (drums).wav", pulse_song(10, [3.0, 7.0]))
    synth.write(folder / "001 - Song (no drums).wav", pulse_song(10, [3.0, 7.0]))
    synth.write(folder / "001 - Song (50%).wav", pulse_song(20, [6.0, 14.0]))
    synth.write(folder / "001 - Song (record 2026-11-01 19-05-12).wav", pulse_song(4, [1.0]))
    original = folder / "001 - Song.opus"
    subprocess.run(["ffmpeg", "-v", "error", "-i", str(folder / "001 - Song (drums).wav"), "-c:a", "libopus",
                    "-b:a", "192k", "-metadata", "purl=https://example.com/watch?v=x", str(original)], check=True)
    trashed = []

    def trash(paths):
        trashed.extend(os.path.basename(p) for p in paths)
        for p in paths:
            os.remove(p)
    monkeypatch.setattr(trim.system, "trash", trash)
    return original, trashed


def test_scale():
    assert trim.scale("Song (drums).wav") == 1 and trim.scale("Song (+2).wav") == 1
    assert trim.scale("Song (80%).wav") == 1.25 and trim.scale("Song (drums) (50%, -2).wav") == 2
    assert trim.scale("Song (record 2026-11-01 19-05-12).wav") is None


def test_same_cut_everywhere_to_the_sample(song):
    original, trashed = song
    folder = original.parent
    trim.run(str(original), start="2", end="8.5", pad_start=0.5, pad_end=0.25, yes=True)
    # Kept 2..8.5 s (6.5 s) + 0.5 s before + 0.25 s after: the pulses at 3 and 7 s are at 1.5 and 5.5 s.
    for name in ("001 - Song (drums).wav", "001 - Song (no drums).wav"):
        assert onsets(folder / name) == pytest.approx([1.5, 5.5], abs=1 / SR)
        assert len(decode(folder / name)) == round(7.25 * SR)
    # The re-encoded original lines up with the stems (Opus can't be cut finer without it).
    assert onsets(folder / "001 - Song.opus") == pytest.approx([1.5, 5.5], abs=0.0005)
    # At 50 % speed, every time doubles.
    assert onsets(folder / "001 - Song (50%).wav") == pytest.approx([3.0, 11.0], abs=1 / SR)
    assert len(decode(folder / "001 - Song (50%).wav")) == round(14.5 * SR)
    # The take isn't touched; the old files went to the trash; nothing left over.
    assert onsets(folder / "001 - Song (record 2026-11-01 19-05-12).wav") == pytest.approx([1.0], abs=1 / SR)
    assert sorted(trashed) == sorted(n + trim.OLD for n in ["001 - Song (drums).wav", "001 - Song (no drums).wav",
                                                             "001 - Song (50%).wav", "001 - Song.opus"])
    assert not [n for n in os.listdir(folder) if n.endswith((trim.NEW, trim.OLD))]
    # 32-bit float stays float (peaks above 0 dB survive), and the download link stays.
    probe = lambda p, what: subprocess.run(["ffprobe", "-v", "error", "-show_entries", what, "-of",
                                            "default=nw=1:nk=1", str(p)], capture_output=True, text=True).stdout
    assert "pcm_f32le" in probe(folder / "001 - Song (drums).wav", "stream=codec_name")
    assert "example.com" in probe(original, "stream_tags=purl:format_tags=purl")


def test_click_and_lyrics_follow(song):
    original, _ = song
    folder = original.parent
    results.save("click", [(str(original), align.describe(120, "4/4", 0.25)),
                           (str(folder / "001 - Song (50%).wav"), align.describe(60, "4/4", 0.5))])
    lyrics.save(original, {"text": "a\nb\nc", "times": {"0": 1.0, "1": 3.5, "2": 6.0},
                           "synced": [[1.0, "a"], [3.5, "b"], [6.0, "c"]]})
    trim.run(str(original), start="2", yes=True)
    clicks = results.read(str(folder), "click")
    # 0.25 - 2 = -1.75: cut off, so moved to the next beat that's still there (every 0.5 s).
    assert align.parse(clicks["001 - Song.opus"])["first"] == pytest.approx(0.25)
    assert align.parse(clicks["001 - Song (50%).wav"])["first"] == pytest.approx(0.5)
    data = json.loads((folder / "001 - Song.lyrics.json").read_text())
    assert data["times"] == {"1": 1.5, "2": 4.0} and data["synced"] == [[1.5, "b"], [4.0, "c"]]


def test_all_or_nothing(song, monkeypatch):
    original, trashed = song
    folder = original.parent
    before = {n: (folder / n).read_bytes() for n in os.listdir(folder)}
    real = trim.ffmpeg_args

    def broken(source, target, *rest):
        args = real(source, target, *rest)
        return args[:-1] + ["/nonexistent/dir/x.wav"] if "(50%)" in source else args
    monkeypatch.setattr(trim, "ffmpeg_args", broken)
    with pytest.raises(SystemExit):
        trim.run(str(original), start="2", yes=True)
    assert {n: (folder / n).read_bytes() for n in os.listdir(folder)} == before and not trashed


@pytest.mark.parametrize("args", [dict(start="9", end="3"), dict(end="99"), dict(pad_start=120), dict()])
def test_refuses(song, args):
    original, trashed = song
    with pytest.raises(SystemExit):
        trim.run(str(original), yes=True, **args)
    assert not trashed
