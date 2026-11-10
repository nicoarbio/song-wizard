"""Functions that need no audio."""

import json
import os
from pathlib import Path

import pytest

from song_wizard import archives, audio, bpm, click, config, key, layout, paths, results, song, ui


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
    "vocals", "no drums", "bass", "no guitar", "other", "piano", "no piano", "kick", "hihat", "drums rest",
    "+2", "-1.5", "80%", "87.5%", "80%, -2", "120%, +1.5", "drums 80%", "no vocals +2", "drums rest 80%, -2",
    "click 120 BPM 4-4", "click 92.5 BPM 6-8 x2", "record 2026-11-01 19-05-12", "record 2026-11-01 19-05-12-001",
]
ORIGINAL_NAMES = ["Song", "001 - Song (2019 Remaster)", "Click Track", "Piano", "drums2", "80", "-80%", "click",
                  "drums and bass", "record", "Song (drums)"]


@pytest.mark.parametrize("name", GENERATED_NAMES)
def test_generated(name):
    assert song.parts(name + ".opus")


@pytest.mark.parametrize("name", ORIGINAL_NAMES)
def test_not_generated(name):
    assert song.parts(name + ".opus") is None


@pytest.mark.parametrize("name, what", [
    ("drums.opus", "stem"), ("no drums.wav", "stem"), ("drums rest.opus", "stem"), ("+2.opus", "version"),
    ("drums 80%.opus", "version"), ("80%, -2.wav", "version"), ("click 120 BPM 4-4.wav", "click"),
    ("record 2026-11-01 19-05-12.wav", "take"), ("001 - Song.opus", None),
])
def test_kind(name, what):
    assert song.kind(name) == what


def test_speed_of():
    assert song.speed_of("drums 80%.opus") == pytest.approx(0.8)
    assert song.speed_of("80% 50%.opus") == pytest.approx(0.4)
    assert song.speed_of("+2.opus") == 1


@pytest.mark.parametrize("name, base", [
    ("Song (drums).wav", "Song"), ("Song (no drums).wav", "Song"), ("Song (+2).wav", "Song"),
    ("Song (other).wav", "Song"), ("Song (drums) (count-in).wav", "Song"), ("Song (count-in).wav", "Song"),
    ("Song (80%).wav", "Song"), ("Song (drums) (80%, -2).wav", "Song"), ("Song.mp3", "Song"), ("Song (Live) (vocals).wav", "Song (Live)"),
    ("Click 120 BPM 4-4.wav", "Click 120 BPM 4-4"), ("Song (click 120 BPM 4-4).wav", "Song"),
    ("Song (drums) (80%) (click 96 BPM 4-4 x2).wav", "Song"),
])
def test_old_base(name, base):
    assert layout.old_base(name) == base


@pytest.mark.parametrize("old, new", [
    ("Song (drums).wav", "drums.wav"), ("Song (drums) (80%).wav", "drums 80%.wav"), ("Song (80%, -2).opus", "80%, -2.opus"),
    ("Song (record 2026-11-01 19-05-12).wav", "record 2026-11-01 19-05-12.wav"), ("Song.wav", "Song.wav"),
    ("Song (click).wav", "Song (click).wav"),
])
def test_old_names_to_new(old, new):
    assert layout.new_name(old, "Song") == new


def test_expand_takes_songs(tmp_path):
    a = tmp_path / "a"
    a.mkdir()
    for name in ["a.opus", "drums.wav", "notes.json"]:
        (a / name).touch()
    (tmp_path / "Click 120 BPM 4-4.wav").touch()
    (tmp_path / "not a song").mkdir()
    assert [os.path.basename(f) for f in audio.expand([str(tmp_path)], skip_generated=True)] == ["a.opus"]
    explicit = str(a / "drums.wav")
    assert audio.expand([explicit]) == [explicit]
    assert audio.expand([explicit], skip_generated=True) == [str(a / "a.opus")]
    assert audio.expand([str(a)]) == [str(a / "a.opus")]


def test_made_names(tmp_path):
    a = tmp_path / "001 - Song"
    a.mkdir()
    (a / "001 - Song.opus").touch()
    assert song.made(a / "001 - Song.opus", "drums").name == "drums.opus"
    assert song.made(a / "drums.opus", "80%").name == "drums 80%.opus"
    assert song.made(a / "001 - Song.wav", "+2", ".wav").name == "+2.wav"


def test_loose_song_is_the_old_layout(tmp_path, capsys):
    (tmp_path / "Song.opus").touch()
    with pytest.raises(SystemExit):
        song.folder(tmp_path / "Song.opus")
    assert "song-wizard tidy" in capsys.readouterr().err


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
    assert config.load() == {"download": {"music_dir": None}, "audio": {"stems": "opus"}, "reaper": {"count_in": 4}}


def test_config_file_values():
    config.CONFIG_PATH.parent.mkdir(parents=True)
    config.CONFIG_PATH.write_text('[download]\nmusic_dir = "~/Ensayos"\n[unknown]\nx = 1\n')
    assert config.load() == {"download": {"music_dir": "~/Ensayos"}, "audio": {"stems": "opus"}, "reaper": {"count_in": 4}}


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


def test_results_one_file_per_song(tmp_path):
    a = tmp_path / "One"
    a.mkdir()
    (a / "One.opus").touch()
    assert results.read(a / "One.opus", "key") is None
    assert results.save(a / "One.opus", "key", "G") == a / "key.txt"
    results.save(a / "One.opus", "key", "Gm")
    assert (a / "key.txt").read_text() == "Gm\n"
    assert results.read(a, "key") == "Gm"
    assert results.by_hand(a, "key") is None
    results.save(a, "tempo", results.hand("120.0 BPM"))
    assert results.by_hand(a, "tempo") == "120.0 BPM  set by hand"


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
        ("PLa", "Alpha", 3), ("PLb", "beta", 2), ("singles", "Singles (single links)", 1)]
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


def test_separate_choose():
    from song_wizard import separate
    # "all" is the four instruments (plus "other"); piano only when asked for, on top.
    assert separate.choose(["all"]) == (["vocals", "drums", "bass", "guitar"], True)
    assert separate.choose(["all", "piano"]) == (["vocals", "drums", "bass", "guitar", "piano"], True)
    assert separate.choose(["piano", "guitar", "piano"]) == (["piano", "guitar"], False)
    # Guitar and piano come from the same model: one pass for both.
    assert separate.MODELS["guitar"][0] == separate.MODELS["piano"][0]


def test_config_gets_the_new_settings():
    """A settings file from an older song-wizard gets the settings it doesn't mention, commented
    out (so nothing changes): in their section, or in a new one at the end. What's written stays."""
    config.CONFIG_PATH.parent.mkdir(parents=True)
    old = '# mine\n[audio]\nstems = "wav"  # I edit them\n\n[download]\nmusic_dir = "~/x"\n'
    config.CONFIG_PATH.write_text(old)
    assert config.ensure() is False
    text = config.CONFIG_PATH.read_text()
    assert text.startswith(old.rstrip("\n")) and "\n[reaper]\n" in text and "\n# count_in = 4\n" in text
    assert config.load()["audio"]["stems"] == "wav" and config.load()["reaper"]["count_in"] == 4
    config.ensure()
    assert config.CONFIG_PATH.read_text() == text  # once
    # A setting missing from a section that's there goes into it.
    config.CONFIG_PATH.write_text('[reaper]\n# count_in = 2\n\n[audio]\n# a note\n\n[download]\n# music_dir = "~/y"\n')
    config.ensure()
    text = config.CONFIG_PATH.read_text()
    audio = text.split("[audio]\n")[1].split("[download]")[0]
    assert audio.startswith("# a note\n# Format of the stems") and '# stems = "opus"\n' in audio
    assert "# count_in = 2" in text and "count_in = 4" not in text
    # A broken file is left alone (load() says what's wrong with it).
    config.CONFIG_PATH.write_text("[audio\n")
    config.ensure()
    assert config.CONFIG_PATH.read_text() == "[audio\n"
