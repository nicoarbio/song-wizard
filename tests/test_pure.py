"""Functions that need no audio."""

import json
import os
from pathlib import Path

import pytest

from song_wizard import archives, audio, bpm, click, config, key, paths, results, ui


@pytest.mark.parametrize("k, scale, expected", [
    ("C", "major", "Am"), ("A", "minor", "C"), ("Eb", "major", "Cm"), ("C", "minor", "Eb"),
    ("F#", "minor", "A"), ("A", "major", "F#m"), ("G#", "minor", "B"), ("B", "major", "G#m"),
])
def test_key_relative(k, scale, expected):
    assert key.relative(k, scale) == expected


def test_key_short():
    assert key.short("Bb", "minor") == "Bbm"
    assert key.short("Bb", "major") == "Bb"


def test_bpm_steady():
    assert bpm.describe(120, 119.5, 120.5, 4.0) == ("steady", True)


def test_bpm_varies():
    note, trusted = bpm.describe(120, 115, 125, 4.0)
    assert trusted and note.startswith("varies 115-125")


def test_bpm_uncertain_suggests_half_and_double():
    note, trusted = bpm.describe(100, 99, 101, 0.5)
    assert not trusted
    assert "50.0 or 200.0" in note


def test_bpm_uncertain_only_plausible_tempos():
    note, _ = bpm.describe(160, 100, 200, 4.0)
    assert "80.0" in note and "320" not in note


GENERATED_NAMES = [
    "Song (vocals)", "Song (no drums)", "Song (bass)", "Song (no guitar)", "Song (other)",
    "Song (+2)", "Song (-1.5)", "Song (80%)", "Song (87.5%)", "Song (80%, -2)", "Song (120%, +1.5)", "Song (click)", "Song (drums) (count-in)", "Song (count-in)",
    "Click 120 BPM 4-4", "Click 92.5 BPM 6-8 x2", "Song (click 120 BPM 4-4)", "Song (80%) (click 96 BPM 3-4 x2)",
]
ORIGINAL_NAMES = ["Song", "Song (Live)", "Song (feat. Someone)", "001 - Song (2019 Remaster)",
                  "Click Track", "Song (piano)", "Song +2", "Song (80)", "Song (-80%)", "Song (click track)"]


@pytest.mark.parametrize("name", GENERATED_NAMES)
def test_generated(name):
    assert audio.GENERATED.search(name)


@pytest.mark.parametrize("name", ORIGINAL_NAMES)
def test_not_generated(name):
    assert not audio.GENERATED.search(name)


@pytest.mark.parametrize("name, base", [
    ("Song (drums).wav", "Song"), ("Song (no drums).wav", "Song"), ("Song (+2).wav", "Song"),
    ("Song (other).wav", "Song"), ("Song (drums) (count-in).wav", "Song"), ("Song (count-in).wav", "Song"),
    ("Song (80%).wav", "Song"), ("Song (drums) (80%, -2).wav", "Song"), ("Song.mp3", "Song"), ("Song (Live) (vocals).wav", "Song (Live)"),
    ("Click 120 BPM 4-4.wav", "Click 120 BPM 4-4"), ("Song (click 120 BPM 4-4).wav", "Song"),
    ("Song (drums) (80%) (click 96 BPM 4-4 x2).wav", "Song"),
])
def test_base_of(name, base):
    assert ui.base_of(name) == base


def test_expand_skips_generated_only_in_folders(tmp_path):
    for name in ["a.opus", "a (drums).wav", "Click 120 BPM 4-4.wav", "notes.txt"]:
        (tmp_path / name).touch()
    assert [os.path.basename(f) for f in audio.expand([str(tmp_path)], skip_generated=True)] == ["a.opus"]
    explicit = str(tmp_path / "a (drums).wav")
    assert list(audio.expand([explicit], skip_generated=True)) == [explicit]


@pytest.mark.parametrize("text, n", [("4/4", (4, 4)), ("3/4", (3, 4)), (" 7 / 8 ", (7, 8)), ("12/8", (12, 8))])
def test_parse_meter(text, n):
    assert click.parse_meter(text) == n


@pytest.mark.parametrize("text", ["4", "0/4", "33/4", "four/4", "4/"])
def test_parse_meter_invalid(text):
    with pytest.raises(SystemExit):
        click.parse_meter(text)


@pytest.mark.parametrize("text, seconds", [("4:30", 270), ("270", 270), ("1:02:00", 3720), ("0:07.5", 7.5)])
def test_parse_duration(text, seconds):
    assert click.parse_duration(text) == seconds


@pytest.mark.parametrize("text", ["", "abc", "1:2:3:4", "-5", "4:-30"])
def test_parse_duration_invalid(text):
    with pytest.raises(SystemExit):
        click.parse_duration(text)


def test_config_defaults():
    assert not config.CONFIG_PATH.exists()
    assert config.load() == {"download": {"music_dir": None}}


def test_config_file_values():
    config.CONFIG_PATH.parent.mkdir(parents=True)
    config.CONFIG_PATH.write_text('[download]\nmusic_dir = "~/Ensayos"\n[unknown]\nx = 1\n')
    assert config.load() == {"download": {"music_dir": "~/Ensayos"}}


def test_config_error():
    config.CONFIG_PATH.parent.mkdir(parents=True)
    config.CONFIG_PATH.write_text("[download\n")
    with pytest.raises(SystemExit) as e:
        config.load()
    assert "Error in" in str(e.value)


def test_config_show_creates_template(capsys):
    config.show()
    assert config.CONFIG_PATH.read_text() == config.TEMPLATE
    assert "Created" in capsys.readouterr().out
    assert config.load()["download"]["music_dir"] is None


def test_music_dir_order(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "is_wsl", lambda: False)
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")
    assert paths.music_dir() == tmp_path / "home" / "Music"
    config.CONFIG_PATH.parent.mkdir(parents=True)
    config.CONFIG_PATH.write_text(f'[download]\nmusic_dir = "{tmp_path / "configured"}"\n')
    assert paths.music_dir() == tmp_path / "configured"
    monkeypatch.setenv("SONG_WIZARD_DIR", str(tmp_path / "env"))
    assert paths.music_dir() == tmp_path / "env"


def read_results(path):
    lines = path.read_text(encoding="utf-8").splitlines()
    assert lines[0].startswith("# song-wizard key")
    return dict(line.split("\t") for line in lines[1:])


def test_results_save_updates_only_those_songs(tmp_path):
    a, b = tmp_path / "a" / "One.opus", tmp_path / "b" / "Two.opus"
    a.parent.mkdir()
    b.parent.mkdir()
    written = results.save("key", [(str(a), "G"), (str(a.with_name("Three.opus")), "Am"), (str(b), "E")])
    assert sorted(written) == sorted([str(a.parent / "key.txt"), str(b.parent / "key.txt")])
    results.save("key", [(str(a), "Gm")])
    assert read_results(a.parent / "key.txt") == {"One.opus": "Gm", "Three.opus": "Am"}
    assert read_results(b.parent / "key.txt") == {"Two.opus": "E"}


def make_archive(archive_id, title, songs):
    archives.ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    (archives.ARCHIVE_DIR / f"{archive_id}.txt").write_text("".join(f"youtube id{i}\n" for i in range(songs)))
    archives.remember(archive_id, f"https://www.youtube.com/playlist?list={archive_id}", title)


def test_archives_entries():
    make_archive("PLb", "beta", 2)
    make_archive("PLa", "Alpha", 3)
    make_archive(archives.SINGLES, None, 1)
    rows = archives.entries()
    assert [(r[0], r[1], r[2]) for r in rows] == [
        ("PLa", "Alpha", 3), ("PLb", "beta", 2), ("singles", "Singles (single videos)", 1)]
    assert json.loads((archives.ARCHIVE_DIR / "singles.json").read_text())["url"] is None


def test_archives_remember_keeps_title():
    make_archive("PLa", "Alpha", 1)
    archives.remember("PLa", "https://new", None)
    assert archives.read_meta("PLa") == {"url": "https://new", "title": "Alpha"}


def test_archives_delete_some():
    make_archive("PLa", "Alpha", 1)
    make_archive("PLb", "Beta", 1)
    make_archive("PLc", "Gamma", 1)
    archives.delete(["1", "3"], yes=True)
    assert [r[0] for r in archives.entries()] == ["PLb"]
    assert sorted(p.name for p in archives.ARCHIVE_DIR.iterdir()) == ["PLb.json", "PLb.txt"]


def test_archives_delete_all():
    make_archive("PLa", "Alpha", 1)
    make_archive("PLb", "Beta", 1)
    archives.delete(["all"], yes=True)
    assert archives.entries() == []


@pytest.mark.parametrize("which", [["4"], ["x"], ["0"]])
def test_archives_delete_invalid(which):
    make_archive("PLa", "Alpha", 1)
    with pytest.raises(SystemExit):
        archives.delete(which, yes=True)
    assert len(archives.entries()) == 1


def test_archives_delete_needs_confirmation_without_terminal(monkeypatch):
    make_archive("PLa", "Alpha", 1)
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    with pytest.raises(SystemExit):
        archives.delete(["all"])
    assert len(archives.entries()) == 1


@pytest.mark.parametrize("line, percent", [
    ("   45%  (2/5) Song.opus", 45), (" 43%|████▎     | 3/7 [00:00<00:00,  7.69it/s]", 43),
    ("[download]  45.3% of    3.40MiB at  1.20MiB/s ETA 00:02", 45.3), ("Running on CPU", None), ("", None),
])
def test_percent_of(line, percent):
    assert ui.percent_of(line) == percent


def test_progress_line(capsys):
    progress = audio.Progress(2)
    progress.update(0, 0, "a.wav")
    progress.update(0, 0.001, "a.wav")  # same text: not printed again
    progress.update(1, 0.5, "b.wav")
    progress.clear()
    out = capsys.readouterr().out
    parts = out.split("\r")
    assert parts[1].strip() == "0%  (1/2) a.wav"
    assert parts[2].strip() == "75%  (2/2) b.wav"
    assert parts[3].strip() == "" and parts[-1] == ""
    assert ui.percent_of(parts[2]) == 75


def test_archives_remember_folder_and_wav(tmp_path):
    make_archive("PLa", "Alpha", 1)
    archives.remember("PLa", "https://www.youtube.com/playlist?list=PLa", None, folder=str(tmp_path / "Alpha"), wav=True)
    archives.remember("PLa", "https://www.youtube.com/playlist?list=PLa", None)  # a later run keeps them
    assert archives.playlists() == [{"id": "PLa", "title": "Alpha", "url": "https://www.youtube.com/playlist?list=PLa",
                                     "folder": str(tmp_path / "Alpha"), "wav": True}]


def test_playlist_for(tmp_path):
    make_archive("PLa", "Show: dic 2026", 1)  # an older archive, without folder: matched by name
    make_archive("PLb", "Other", 1)
    archives.remember("PLb", "https://www.youtube.com/playlist?list=PLb", None, folder=str(tmp_path / "Renamed"))
    make_archive(archives.SINGLES, None, 1)
    assert archives.playlist_for(tmp_path / "Show： dic 2026")["id"] == "PLa"
    assert archives.playlist_for(tmp_path / "Renamed")["id"] == "PLb"
    assert archives.playlist_for(tmp_path / "Other") is None  # PLb has its folder: no guessing
    assert archives.playlist_for(tmp_path / "Singles") is None
