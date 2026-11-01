"""Playlists kept anywhere: moving them, and Windows paths."""

import json

import pytest

from song_wizard import archives, system


@pytest.fixture
def playlist(tmp_path, monkeypatch):
    music = tmp_path / "music"
    show = music / "Show"
    show.mkdir(parents=True)
    (show / "001 - A.opus").write_bytes(b"a")
    (show / "001 - A (drums).wav").write_bytes(b"d")
    (show / "key.txt").write_text("# h\n001 - A.opus\tG\n")
    monkeypatch.setenv("SONG_WIZARD_DIR", str(music))
    archives.ARCHIVE_DIR.mkdir(parents=True)
    (archives.ARCHIVE_DIR / "PLx.txt").write_text("site a\n")
    archives.remember("PLx", "https://example.com/playlist?list=PLx", "Show", folder=str(show))
    return show


def recorded():
    return json.loads((archives.ARCHIVE_DIR / "PLx.json").read_text())["folder"]


def test_move(playlist, tmp_path):
    drive = tmp_path / "drive"
    drive.mkdir()
    archives.move("1", str(drive))
    assert not playlist.exists()
    assert sorted(p.name for p in (drive / "Show").iterdir()) == ["001 - A (drums).wav", "001 - A.opus", "key.txt"]
    assert recorded() == str(drive / "Show")
    back = tmp_path / "music"
    archives.move("PLx", str(back))  # by id too
    assert recorded() == str(back / "Show") and (back / "Show" / "001 - A.opus").exists()


def test_moved_by_hand(playlist, tmp_path):
    drive = tmp_path / "drive"
    drive.mkdir()
    playlist.rename(drive / "Show")
    archives.move("1", str(drive))
    assert recorded() == str(drive / "Show")


def test_old_archive_found_by_name(playlist, tmp_path):
    meta = json.loads((archives.ARCHIVE_DIR / "PLx.json").read_text())
    del meta["folder"]
    (archives.ARCHIVE_DIR / "PLx.json").write_text(json.dumps(meta))
    drive = tmp_path / "drive"
    drive.mkdir()
    archives.move("1", str(drive))
    assert (drive / "Show" / "001 - A.opus").exists() and recorded() == str(drive / "Show")


@pytest.mark.parametrize("which, dest", [("7", "drive"), ("PLnope", "drive"), ("1", "missing")])
def test_move_refuses(playlist, tmp_path, which, dest):
    (tmp_path / "drive").mkdir()
    with pytest.raises(SystemExit):
        archives.move(which, str(tmp_path / dest))
    assert playlist.exists()


def test_move_refuses_to_overwrite(playlist, tmp_path):
    (tmp_path / "drive" / "Show").mkdir(parents=True)
    with pytest.raises(SystemExit):
        archives.move("1", str(tmp_path / "drive"))
    assert playlist.exists() and recorded() == str(playlist)


def test_local_path(monkeypatch):
    monkeypatch.setattr(system, "is_wsl", lambda: True)
    monkeypatch.setattr(system.shutil, "which", lambda name: "/usr/bin/wslpath")

    class Out:
        stdout = "/mnt/g/Mi unidad/Ensayos\n"

    monkeypatch.setattr(system.subprocess, "run", lambda cmd, **k: Out() if cmd[:2] == ["wslpath", "-u"] else None)
    assert system.local_path(' "G:\\Mi unidad\\Ensayos" ') == "/mnt/g/Mi unidad/Ensayos"
    assert system.local_path("/srv/music") == "/srv/music"
    monkeypatch.setattr(system, "is_wsl", lambda: False)
    assert system.local_path("G:\\x") == "G:\\x"
