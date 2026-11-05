"""Stems and versions are MP3 by default ([audio] stems in the settings); Opus and WAV on request."""

import os
import subprocess

import synth
from song_wizard import audio, config, transpose


def write_settings(text):
    config.CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    config.CONFIG_PATH.write_text(text)


def test_default_is_mp3():
    assert audio.stem_ext() == ".mp3"
    assert audio.output_path("/music/Song.opus", "drums") == os.path.join("/music", "Song (drums).mp3")


def test_settings_choose_the_format_and_bad_values_fall_back():
    write_settings('[audio]\nstems = "WAV"\n')
    assert audio.stem_ext() == ".wav"
    write_settings('[audio]\nstems = "opus"\n')
    assert audio.stem_ext() == ".opus"
    write_settings('[audio]\nstems = "flac"\n')
    assert audio.stem_ext() == ".mp3"  # not a format for stems: the default


def test_mp3_save_is_small_and_reads_back_at_its_rate(tmp_path):
    tone = synth.sine(440, 3, peak=0.5)
    out = tmp_path / "Song (drums).mp3"
    audio.save(str(out), tone, synth.SR)
    assert out.stat().st_size < 3 * synth.SR * 4 / 10  # far under the 32-bit WAV of the same
    back, sr = audio.load(str(out))
    assert sr == synth.SR
    assert abs(back.shape[1] / sr - 3) < 0.1
    assert abs(float(abs(back).max()) - 0.5) < 0.05  # the level survives the lossy coding


def test_opus_save_still_works(tmp_path):
    out = tmp_path / "Song (drums).opus"
    audio.save(str(out), synth.sine(440, 2, peak=0.5), synth.SR)
    back, sr = audio.load(str(out))
    assert sr == 48000 and abs(back.shape[1] / sr - 2) < 0.05


def test_stem_path_finds_any_format(tmp_path):
    song = tmp_path / "001 - Song.opus"
    song.write_bytes(b"")
    assert audio.stem_path(song, "bass") is None
    (tmp_path / "001 - Song (bass).wav").write_bytes(b"")  # made before the change
    assert audio.stem_path(song, "bass").name == "001 - Song (bass).wav"
    (tmp_path / "001 - Song (bass).mp3").write_bytes(b"")  # the chosen format wins
    assert audio.stem_path(song, "bass").name == "001 - Song (bass).mp3"


def test_versions_are_mp3_by_default(tmp_path):
    src = synth.write(tmp_path / "tone.wav", synth.sine(440, 2))
    transpose.run(1, [str(src)])
    assert sorted(os.listdir(tmp_path)) == ["tone (+1).mp3", "tone.wav"]
    codec = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries",
                            "stream=codec_name", "-of", "csv=p=0", str(tmp_path / "tone (+1).mp3")],
                           capture_output=True, text=True, check=True).stdout.strip()
    assert codec == "mp3"
