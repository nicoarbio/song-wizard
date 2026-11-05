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
    assert sorted(p.name for p in (drive / "Show").iterdir()) == [archives.RECORD, "001 - A (drums).wav", "001 - A.opus", "key.txt"]
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


def test_unmounted_drive(playlist, monkeypatch):
    monkeypatch.setattr(system, "is_wsl", lambda: True)
    monkeypatch.setattr(system.shutil, "which", lambda name: None)  # no wslpath: the fallback
    assert system.local_path("H:\\Mi unidad\\Bateria") == "/mnt/h/Mi unidad/Bateria"
    monkeypatch.setattr(system.os.path, "ismount", lambda p: p == "/mnt/c")
    assert system.unmounted_drive("/mnt/h/Mi unidad/Bateria") == "H"
    assert system.unmounted_drive("/mnt/c/Users") is None
    assert system.unmounted_drive("/home/me") is None
    assert "sudo mount -t drvfs H: /mnt/h -o metadata,uid=" in system.mount_hint("H")  # metadata: chmod works
    with pytest.raises(SystemExit) as e:
        archives.move("1", "/mnt/h/Mi unidad")
    assert "drvfs H:" in str(e.value)


def test_a_place_that_isnt_there_is_shown(tmp_path, monkeypatch, capsys):
    """Singles downloaded to a drive that isn't connected now (Google Drive's, on WSL after a
    restart) used to just vanish from the library."""
    from song_wizard import listing, ui
    music = tmp_path / "music"
    music.mkdir()
    monkeypatch.setenv("SONG_WIZARD_DIR", str(music))
    drive = tmp_path / "drive" / "song-wizard"
    (drive / "Singles").mkdir(parents=True)
    (drive / "Singles" / "Song.opus").write_bytes(b"x")
    archives.ARCHIVE_DIR.mkdir(parents=True)
    archives.remember(archives.SINGLES, None, None, folder=str(drive / "Singles"))
    names = lambda: [(f["name"], bool(f.get("missing"))) for f in ui.library(music)]
    assert names() == [("Singles", False)]
    # Moved away by hand: said, with no drive to connect.
    (tmp_path / "drive").rename(tmp_path / "elsewhere")
    gone = ui.library(music)[-1]
    assert names() == [("song-wizard", True)] and gone["missing"] == {"drive": None, "command": None, "fstab": None}
    # A Windows drive WSL doesn't see: with the command that connects it.
    monkeypatch.setattr(system, "unmounted_drive", lambda path: "H")
    gone = ui.library(music)[-1]
    assert gone["missing"] == {"drive": "H", "command": f"sudo mkdir -p /mnt/h && sudo mount -t drvfs H: /mnt/h -o {system.mount_options()}",
                               "fstab": f"H: /mnt/h drvfs defaults,nofail,{system.mount_options()} 0 0"}
    listing.run()
    assert "(not available: WSL doesn't see drive H:. Connect it with: sudo mkdir -p /mnt/h" in capsys.readouterr().out
