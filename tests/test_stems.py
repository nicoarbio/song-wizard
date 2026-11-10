"""Stems and versions are Opus by default ([audio] stems in the settings); WAV and MP3 on request."""

import os
import subprocess

import synth
from song_wizard import audio, config, transpose


def write_settings(text):
    config.CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    config.CONFIG_PATH.write_text(text)


def test_default_is_opus(tmp_path):
    assert audio.stem_ext() == ".opus"
    (tmp_path / "Song").mkdir()
    (tmp_path / "Song" / "Song.opus").write_bytes(b"")
    assert audio.output_path(tmp_path / "Song" / "Song.opus", "drums") == str(tmp_path / "Song" / "drums.opus")


def test_settings_choose_the_format_and_bad_values_fall_back():
    write_settings('[audio]\nstems = "MP3"\n')
    assert audio.stem_ext() == ".mp3"
    write_settings('[audio]\nstems = "opus"\n')
    assert audio.stem_ext() == ".opus"
    write_settings('[audio]\nstems = "flac"\n')
    assert audio.stem_ext() == ".opus"  # not a format for stems: the default


def test_mp3_save_is_small_and_reads_back_at_its_rate(tmp_path):
    tone = synth.sine(440, 3, peak=0.5)
    out = tmp_path / "Song (drums).mp3"
    audio.save(str(out), tone, synth.SR)
    assert out.stat().st_size < 3 * synth.SR * 4 / 10  # far under the 32-bit WAV of the same
    back, sr = audio.load(str(out))
    assert sr == synth.SR
    assert abs(back.shape[1] / sr - 3) < 0.1
    assert abs(float(abs(back).max()) - 0.5) < 0.05  # the level survives the lossy coding


def test_opus_is_small_and_keeps_peaks_above_0_db(tmp_path):
    """Like the 32-bit float WAV: a stem louder than 0 dB comes back as loud, not clipped (Opus is
    a float codec), so the stems keep adding up to the song."""
    out = tmp_path / "Song (drums).opus"
    audio.save(str(out), synth.sine(440, 2, peak=1.5), synth.SR)
    assert out.stat().st_size < 2 * synth.SR * 2 * 4 / 10
    back, sr = audio.load(str(out))
    assert sr == 48000 and abs(back.shape[1] / sr - 2) < 0.05  # Opus runs at 48 kHz
    assert abs(float(abs(back).max()) - 1.5) < 0.05


def test_stem_path_finds_any_format(tmp_path):
    here = tmp_path / "001 - Song"
    here.mkdir()
    song = here / "001 - Song.opus"
    song.write_bytes(b"")
    assert audio.stem_path(song, "bass") is None
    (here / "bass.wav").write_bytes(b"")  # made before the change
    assert audio.stem_path(song, "bass").name == "bass.wav"
    (here / "bass.opus").write_bytes(b"")
    assert audio.stem_path(song, "bass").name == "bass.opus"  # the chosen format wins
    (here / "bass.mp3").write_bytes(b"")
    write_settings('[audio]\nstems = "mp3"\n')
    assert audio.stem_path(song, "bass").name == "bass.mp3"


def test_versions_in_mp3_when_asked(tmp_path):
    write_settings('[audio]\nstems = "mp3"\n')
    tmp_path = tmp_path / "music"  # the settings live in tmp_path too
    tmp_path.mkdir()
    src = synth.song(tmp_path, "tone.wav", synth.sine(440, 2))
    transpose.run(1, [str(src)])
    assert sorted(os.listdir(src.parent)) == ["+1.mp3", "tone.wav"]
    codec = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries",
                            "stream=codec_name", "-of", "csv=p=0", str(src.parent / "+1.mp3")],
                           capture_output=True, text=True, check=True).stdout.strip()
    assert codec == "mp3"


def test_all_stems_add_up_to_the_original_in_mp3(tmp_path, monkeypatch):
    """"all" makes "other" as the mix minus the stems as stored (MP3, a few samples longer than
    the source). The models are replaced by a fake split: the arithmetic and the files are real."""
    import numpy as np
    import soundfile as sf

    from song_wizard import separate

    def fake_split(model, wanted, inputs, device, tmp, keep):
        for f, scale, path in inputs:
            mix, _ = sf.read(path, dtype="float32", always_2d=True)
            mix = mix.T / scale
            keep(f, mix, {stem: mix * (0.1 * (i + 1)) for i, (stem, _) in enumerate(wanted)})
        return device

    monkeypatch.setattr(separate, "separate_with", fake_split)
    monkeypatch.setattr(separate, "pick", lambda *a, **k: "cpu")
    write_settings('[audio]\nstems = "mp3"\n')
    src = synth.song(tmp_path, "song.wav", synth.sine(330, 3, peak=0.5))
    separate.run(["all"], [str(src)], force_cpu=True)
    original, _ = sf.read(src, dtype="float32", always_2d=True)
    total = np.zeros_like(original)
    for stem in ["vocals", "drums", "bass", "guitar", "other"]:
        part = audio.load(str(src.parent / f"{stem}.mp3"), sr=synth.SR)[0].T
        total[: len(part)] += part[: len(original)]
    assert os.path.exists(src.parent / "other.mp3")
    assert np.abs(total - original).max() < 0.01  # MP3 coding noise only
