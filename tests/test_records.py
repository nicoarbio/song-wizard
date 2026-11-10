"""Each playlist's folder carries its record, so another computer (or a synced drive) knows it."""

import json
import shutil

import pytest

from song_wizard import archives, download, ui

URL = "https://www.youtube.com/playlist?list=PLx"


def record_of(folder):
    return json.loads((folder / archives.RECORD).read_text())


def forget_this_computer():
    """Another computer: nothing downloaded there yet."""
    shutil.rmtree(archives.ARCHIVE_DIR)


@pytest.fixture
def show(tmp_path, monkeypatch):
    """A playlist downloaded into the music folder (with yt-dlp faked: no network)."""
    music = tmp_path / "music"
    folder = music / "Show"
    monkeypatch.setenv("SONG_WIZARD_DIR", str(music))
    folder.mkdir(parents=True)
    (folder / "001 - A").mkdir()
    (folder / "001 - A" / "001 - A.opus").write_bytes(b"a")
    archives.ARCHIVE_DIR.mkdir(parents=True)
    (archives.ARCHIVE_DIR / "PLx.txt").write_text("youtube id1\nyoutube id2\n")
    archives.remember("PLx", URL, "Show", folder=str(folder), wav=True)
    return folder


def test_the_folder_keeps_the_record(show):
    record = record_of(show)
    assert (record["id"], record["title"], record["url"], record["wav"]) == ("PLx", "Show", URL, True)
    assert record["downloaded"] == ["youtube id1", "youtube id2"]


def test_downloading_updates_it(show, monkeypatch):
    seen = []

    class Done:
        returncode = 0

    def run(args, **kw):
        if "--flat-playlist" in args:  # going over the playlist first: here, as if offline
            return __import__("subprocess").CompletedProcess(args, 1, "", "offline")
        archive = archives.ARCHIVE_DIR / "PLx.txt"
        seen.append(archive.read_text())
        archive.write_text(archive.read_text() + "youtube id9\n")
        return Done()

    monkeypatch.setattr(download.subprocess, "run", run)
    monkeypatch.setattr(download, "node_ok", lambda: False)
    # Another computer downloaded a song into the (synced) folder: yt-dlp has to know it.
    record = record_of(show)
    record["downloaded"].append("youtube id3")
    (show / archives.RECORD).write_text(json.dumps(record))
    assert download.fetch(URL) == 0
    assert seen == ["youtube id1\nyoutube id2\nyoutube id3\n"]
    assert record_of(show)["downloaded"] == ["youtube id1", "youtube id2", "youtube id3", "youtube id9"]


def test_another_computer_takes_it_from_the_library(show, tmp_path):
    forget_this_computer()
    assert archives.playlists() == []
    folders = ui.library(tmp_path / "music")
    (playlist,) = archives.playlists()
    assert playlist == {"id": "PLx", "title": "Show", "url": URL, "folder": str(show), "wav": True}
    assert archives.downloaded("PLx") == ["youtube id1", "youtube id2"]
    assert next(f for f in folders if f["name"] == "Show")["playlist"]["id"] == "PLx"


def test_a_folder_outside_the_music_folder(show, tmp_path, capsys):
    drive = tmp_path / "drive"
    drive.mkdir()
    show.rename(drive / "Show")
    forget_this_computer()
    archives.add(str(drive))
    assert "Show: looking for new songs" in capsys.readouterr().out
    assert archives.playlists()[0]["folder"] == str(drive / "Show")
    assert drive in archives.places()
    assert any(f["name"] == "Show" and f["songs"] for f in ui.library(tmp_path / "music"))


def test_adding_a_folder_without_records(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("SONG_WIZARD_DIR", str(tmp_path / "music"))
    (tmp_path / "music").mkdir()
    songs = tmp_path / "copied"
    songs.mkdir()
    (songs / "A.opus").write_bytes(b"a")
    archives.add(str(songs))
    assert "No playlists recorded" in capsys.readouterr().out
    assert songs in archives.places() and archives.playlists() == []


def test_a_copy_doesnt_take_over(show, tmp_path):
    copy = tmp_path / "copy" / "Show"
    shutil.copytree(show, copy)
    assert archives.adopt(copy) is None
    assert archives.playlists()[0]["folder"] == str(show)


def test_moved_by_hand_is_found(show, tmp_path):
    moved = show.with_name("Show (2026)")
    show.rename(moved)
    ui.library(tmp_path / "music")
    assert archives.playlists()[0]["folder"] == str(moved)


def test_forgetting_takes_the_record_too(show, tmp_path):
    archives.forget_sources(["https://www.youtube.com/watch?v=id1"])
    assert record_of(show)["downloaded"] == ["youtube id2"]
    archives.delete(["1"], yes=True)
    assert not (show / archives.RECORD).exists()
    ui.library(tmp_path / "music")
    assert archives.playlists() == []


def test_records_from_before_get_written(show, tmp_path):
    (show / archives.RECORD).unlink()
    ui.library(tmp_path / "music")
    assert record_of(show)["id"] == "PLx"


@pytest.mark.parametrize("record", ['{"id": "../../evil", "downloaded": ["youtube a"]}', "not json", "[]"])
def test_a_bad_record_is_ignored(tmp_path, record):
    folder = tmp_path / "Show"
    folder.mkdir()
    (folder / archives.RECORD).write_text(record)
    assert archives.adopt(folder) is None
    assert not archives.ARCHIVE_DIR.exists() or not list(archives.ARCHIVE_DIR.iterdir())


def test_a_strange_url_isnt_kept(tmp_path):
    folder = tmp_path / "Show"
    folder.mkdir()
    (folder / archives.RECORD).write_text(json.dumps({"id": "PLy", "url": "file:///etc/passwd", "title": "S"}))
    assert archives.adopt(folder) == "PLy"
    assert archives.playlists() == []  # without a link there's nothing to look in


def test_a_folder_inside_a_place_isnt_shown_twice(tmp_path, monkeypatch):
    """"add folder" on a folder that's already one of a place's folders: it stays one folder."""
    monkeypatch.setenv("SONG_WIZARD_DIR", str(tmp_path / "music"))
    (tmp_path / "music").mkdir()
    drive = tmp_path / "drive"
    inside = drive / "Inéditos" / "Song"
    inside.mkdir(parents=True)
    (inside / "Song.opus").write_bytes(b"x")
    archives.add_place(drive)
    archives.add_place(drive / "Inéditos")  # as "add folder" did
    assert archives.places() == [drive]
    archives.places_file().write_text(f"{drive}\n{drive / 'Inéditos'}\n")  # added by an older version
    assert archives.places() == [drive]
    assert [f["name"] for f in ui.library(tmp_path / "music")] == ["Inéditos"]
