"""song-wizard uninstall: removes what it keeps outside the music folder and then itself (uv tool
uninstall, last), never the music; asks first; --keep-data removes only the program."""

import pytest

from song_wizard import config, paths, reaper, ui, uninstall


@pytest.fixture
def place(tmp_path, monkeypatch):
    data = tmp_path / "data" / "song-wizard"
    (data / "models").mkdir(parents=True)
    (data / "models" / "model.ckpt").write_bytes(b"x" * 2048)
    (data / "archives").mkdir()
    (data / "archives" / "playlist.txt").write_text("youtube abc\n")
    (data / "logs").mkdir()
    (data / "logs" / "song-wizard.log").write_text("log\n")
    settings = tmp_path / "config" / "song-wizard"
    settings.mkdir(parents=True)
    (settings / "config.toml").write_text("")
    music = tmp_path / "music"
    music.mkdir()
    (music / "001 - Song.opus").write_bytes(b"x")
    program = tmp_path / "tools" / "song-wizard"
    program.mkdir(parents=True)
    monkeypatch.setattr(paths, "DATA_DIR", data)
    monkeypatch.setattr(paths, "MODELS_DIR", data / "models")
    monkeypatch.setattr(paths, "ARCHIVE_DIR", data / "archives")
    monkeypatch.setattr(config, "CONFIG_PATH", settings / "config.toml")
    monkeypatch.setenv("SONG_WIZARD_DIR", str(music))
    monkeypatch.setattr(uninstall, "program_dir", lambda: program)
    monkeypatch.setattr(ui, "running", lambda: None)
    monkeypatch.setattr(reaper, "setting", lambda: {"changed": None})
    calls = []
    monkeypatch.setattr(uninstall.os, "execvp", lambda f, args: calls.append(args))
    return {"data": data, "settings": settings, "music": music, "calls": calls}


def test_removes_data_settings_then_program(place, capsys):
    uninstall.run(yes=True)
    out = capsys.readouterr().out
    assert "the separation models" in out and "(2 KB)" in out
    assert "download all of it again" in out  # there was a record of downloads
    assert not place["data"].exists() and not place["settings"].exists()
    assert (place["music"] / "001 - Song.opus").exists()
    assert place["calls"] == [["uv", "tool", "uninstall", "song-wizard"]]


def test_keep_data_removes_only_the_program(place):
    uninstall.run(keep_data=True, yes=True)
    assert (place["data"] / "models" / "model.ckpt").exists() and place["settings"].exists()
    assert place["calls"] == [["uv", "tool", "uninstall", "song-wizard"]]


def test_doesnt_remove_without_asking(place, monkeypatch):
    monkeypatch.setattr(uninstall.sys.stdin, "isatty", lambda: False)
    with pytest.raises(SystemExit):
        uninstall.run()
    assert place["data"].exists() and place["calls"] == []


def test_no_is_no(place, monkeypatch):
    monkeypatch.setattr(uninstall.sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda q: "")
    uninstall.run()
    assert place["data"].exists() and place["calls"] == []


def test_puts_reaper_back(place, monkeypatch):
    monkeypatch.setattr(reaper, "setting", lambda: {"changed": "2026-11-01 10:00", "before": None})
    done = []
    monkeypatch.setattr(reaper, "restore", lambda: done.append(1) or "restored")
    uninstall.run(yes=True)
    assert done == [1]


def test_stops_short_if_the_interface_stays(place, monkeypatch):
    monkeypatch.setattr(ui, "running", lambda: {"pid": 1})
    monkeypatch.setattr(ui, "stop", lambda yes=False: False)
    uninstall.run(yes=True)
    assert place["data"].exists() and place["calls"] == []
