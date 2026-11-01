"""delete: to the trash, a song with everything made from it, or single files."""

import os
import subprocess

import pytest

import synth
from song_wizard import archives, delete, results, system

LINK = "https://example.com/watch?v=abc123"


@pytest.fixture
def trash(tmp_path, monkeypatch):
    """The trash is a folder here; files that would go are moved into it."""
    bin_ = tmp_path / "trash"
    bin_.mkdir()

    def fake(paths):
        for p in paths:
            os.rename(p, bin_ / os.path.basename(p))

    monkeypatch.setattr(system, "trash", fake)
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    return bin_


@pytest.fixture
def show(tmp_path):
    folder = tmp_path / "Show"
    folder.mkdir()
    synth.write(folder / "tone.wav", synth.sine(440, 1))
    # A downloaded song keeps its link in the "purl" tag, as yt-dlp writes it.
    subprocess.run(["ffmpeg", "-v", "error", "-i", str(folder / "tone.wav"), "-c:a", "libopus",
                    "-metadata", f"purl={LINK}", str(folder / "001 - Song.opus")], check=True)
    os.remove(folder / "tone.wav")
    for name in ["001 - Song.wav", "001 - Song (drums).wav", "001 - Song (80%).wav",
                 "001 - Song (click 120 BPM 4-4).wav", "002 - Other.opus"]:
        (folder / name).write_bytes(b"x")
    for command in ("key", "bpm", "click"):
        results.save(command, [(str(folder / "001 - Song.opus"), "a"), (str(folder / "001 - Song (drums).wav"), "b"),
                               (str(folder / "002 - Other.opus"), "c")])
    archives.ARCHIVE_DIR.mkdir(parents=True)
    (archives.ARCHIVE_DIR / "PLx.txt").write_text("site abc123\nsite other1\n")
    return folder


def test_source_link(show):
    assert delete.source_link(str(show / "001 - Song.opus")) == LINK
    assert delete.source_link(str(show / "001 - Song.wav")) is None


def test_delete_song(show, trash):
    delete.run(songs=[str(show / "001 - Song.opus")], yes=True)
    assert sorted(os.listdir(show)) == ["002 - Other.opus", "bpm.txt", "click.txt", "key.txt"]
    assert len(os.listdir(trash)) == 5
    for command in ("key", "bpm", "click"):
        assert results.read(str(show), command) == {"002 - Other.opus": "c"}
    assert (archives.ARCHIVE_DIR / "PLx.txt").read_text() == "site other1\n"


def test_delete_single_files(show, trash):
    delete.run(files=[str(show / "001 - Song.wav")], songs=[str(show / "001 - Song (drums).wav")], yes=True)
    assert sorted(os.listdir(trash)) == ["001 - Song (drums).wav", "001 - Song.wav"]
    assert (show / "001 - Song.opus").exists() and (show / "001 - Song (80%).wav").exists()
    assert results.read(str(show), "key") == {"001 - Song.opus": "a", "002 - Other.opus": "c"}
    assert "abc123" in (archives.ARCHIVE_DIR / "PLx.txt").read_text()


def test_needs_confirmation(show, trash):
    with pytest.raises(SystemExit):
        delete.run(songs=[str(show / "001 - Song.opus")])
    assert os.listdir(trash) == []


def test_trash_failure_touches_nothing_else(show, monkeypatch):
    def failing(paths):
        raise system.TrashError("could not move to the trash: x")

    monkeypatch.setattr(system, "trash", failing)
    with pytest.raises(SystemExit):
        delete.run(songs=[str(show / "001 - Song.opus")], yes=True)
    assert results.read(str(show), "key")["001 - Song.opus"] == "a"
    assert "abc123" in (archives.ARCHIVE_DIR / "PLx.txt").read_text()


def test_missing(tmp_path, trash):
    with pytest.raises(SystemExit):
        delete.run(files=[str(tmp_path / "nope.wav")], yes=True)


def test_desktop_trash(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    for i in range(2):
        f = tmp_path / "song.wav"
        f.write_bytes(b"x")
        system.desktop_trash(str(f))
    files = tmp_path / "data" / "Trash" / "files"
    assert sorted(os.listdir(files)) == ["song.2.wav", "song.wav"]
    info = (tmp_path / "data" / "Trash" / "info" / "song.wav.trashinfo").read_text()
    assert info.startswith("[Trash Info]\nPath=") and str(tmp_path).replace(" ", "%20") in info


def test_trash_picks_the_right_bin(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(system, "is_wsl", lambda: True)
    monkeypatch.setattr(system, "windows_trash", lambda paths: calls.append(("windows", paths)))
    monkeypatch.setattr(system.sys, "platform", "linux")
    monkeypatch.setattr(system.shutil, "which", lambda name: None)
    monkeypatch.setattr(system, "desktop_trash", lambda p: calls.append(("desktop", p)))
    linux = tmp_path / "a.wav"
    system.trash(["/mnt/c/Users/me/Music/b.wav", str(linux)])  # neither exists: nothing is left over
    assert calls == [("windows", ["/mnt/c/Users/me/Music/b.wav"]), ("desktop", str(linux))]
