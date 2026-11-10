"""Songs added by hand to a playlist's folder take the number after the last one, and songs
downloaded later go on from there."""

import os
import subprocess
import time
from pathlib import Path

import pytest

from song_wizard import archives, download, numbering, tags, ui

URL = "https://www.youtube.com/playlist?list=PLx"


def tone(path, **fields):
    command = ["ffmpeg", "-nostdin", "-v", "error", "-y", "-f", "lavfi", "-i", "sine=d=0.3"]
    for k, v in fields.items():
        command += ["-metadata", f"{k}={v}"]
    subprocess.run([*command, str(path)], check=True)
    return path


def settled(*paths, ago=120):
    for p in paths:
        os.utime(p, (time.time() - ago, time.time() - ago))


def names(folder):
    """The folder's songs as "song/file" (and loose files by name)."""
    return sorted(str(p.relative_to(folder)) for p in folder.rglob("*")
                  if p.is_file() and not p.name.startswith("."))


def song(folder, name, **fields):
    here = folder / Path(name).stem
    here.mkdir(parents=True, exist_ok=True)
    return tone(here / name, **fields)


@pytest.fixture
def show(tmp_path, monkeypatch):
    music = tmp_path / "music"
    folder = music / "Show"
    folder.mkdir(parents=True)
    monkeypatch.setenv("SONG_WIZARD_DIR", str(music))
    song(folder, "001 - A.opus")
    song(folder, "002 - B.opus")
    archives.ARCHIVE_DIR.mkdir(parents=True)
    (archives.ARCHIVE_DIR / "PLx.txt").write_text("youtube a\nyoutube b\n")
    archives.remember("PLx", URL, "Show", folder=str(folder))
    return folder


def test_added_by_hand_takes_the_next_number(show):
    first = tone(show / "Recording.mp3")  # dropped in the playlist's folder
    second = song(show, "Tagged.wav", title="Song", artist="Band")  # or in a folder of its own
    (second.parent / "drums.wav").write_bytes(second.read_bytes())
    (second.parent / "key.txt").write_text("G\n")
    settled(first, ago=200)
    settled(second, ago=100)
    done = numbering.tidy(show)
    assert [p.name for p in done] == ["003 - Recording.mp3", "004 - Band - Song.wav"]
    assert names(show) == ["001 - A/001 - A.opus", "002 - B/002 - B.opus", "003 - Recording/003 - Recording.mp3",
                           "004 - Band - Song/004 - Band - Song.wav", "004 - Band - Song/drums.wav",
                           "004 - Band - Song/key.txt"]
    assert "encoded_by" not in tags.read(show / "003 - Recording" / "003 - Recording.mp3")  # song-wizard didn't make it


def test_still_coming_in_waits(show):
    tone(show / "Copying.mp3")
    assert numbering.tidy(show) == []
    assert "Copying.mp3" in names(show)  # loose, until it's all there


def test_its_wav_if_the_playlist_keeps_them(show):
    settled(tone(show / "Recording.mp3"))
    numbering.tidy(show, wav=True)
    assert {"003 - Recording/003 - Recording.mp3", "003 - Recording/003 - Recording.wav"} <= set(names(show))


def test_the_library_numbers_them(show, tmp_path):
    settled(tone(show / "Recording.mp3"))
    folders = ui.library(tmp_path / "music")
    (folder,) = [f for f in folders if f["name"] == "Show"]
    assert [s["name"] for s in folder["songs"]] == ["001 - A.opus", "002 - B.opus", "003 - Recording.mp3"]


def test_not_outside_playlists(tmp_path, monkeypatch):
    music = tmp_path / "music"
    (music / "Singles").mkdir(parents=True)
    monkeypatch.setenv("SONG_WIZARD_DIR", str(music))
    settled(tone(music / "Singles" / "Loose.mp3"))
    ui.library(music)
    assert names(music / "Singles") == ["Loose/Loose.mp3"]  # to its folder, without a number


def test_keeps_the_digits(tmp_path):
    folder = tmp_path / "Long"
    folder.mkdir()
    song(folder, "0099 - A.opus")
    settled(tone(folder / "New.opus"))
    assert [p.name for p in numbering.tidy(folder)] == ["0100 - New.opus"]


def fake_ytdlp(monkeypatch, make):
    class Done:
        returncode = 0

    real = subprocess.run

    def run(args, **kw):
        if "yt_dlp" not in args:  # ffmpeg, making the test's files
            return real(args, **kw)
        prints = {args[i + 1]: args[i + 2] for i, a in enumerate(args) if a == "--print-to-file"}
        Path(prints["playlist:%(title)s"]).write_text("Show\n")
        made = make()
        Path(prints["after_move:%(filepath)s"]).write_text("".join(f"{p}\n" for p in made))
        return Done()

    monkeypatch.setattr(download.subprocess, "run", run)
    monkeypatch.setattr(download, "node_ok", lambda: False)


def test_downloads_go_after_the_last(show, monkeypatch):
    settled(tone(show / "Recording.mp3"))  # by hand, still unnumbered: it goes first
    # Added 2nd in the site's playlist: yt-dlp names it by that place.
    fake_ytdlp(monkeypatch, lambda: [tone(show / "002 - New.opus"), tone(show / "005 - Other.opus")])
    assert download.fetch(URL) == 0
    assert names(show) == ["001 - A/001 - A.opus", "002 - B/002 - B.opus", "003 - Recording/003 - Recording.mp3",
                           "004 - New/004 - New.opus", "005 - Other/005 - Other.opus"]


def test_a_new_playlist_keeps_the_sites_order(tmp_path, monkeypatch):
    music = tmp_path / "music"
    monkeypatch.setenv("SONG_WIZARD_DIR", str(music))

    def make():
        (music / "Show").mkdir(parents=True)
        return [tone(music / "Show" / "001 - A.opus"), tone(music / "Show" / "002 - B.opus")]

    fake_ytdlp(monkeypatch, make)
    assert download.fetch(URL) == 0
    assert names(music / "Show") == ["001 - A/001 - A.opus", "002 - B/002 - B.opus"]


def test_reorder(show):
    c = song(show, "003 - C.opus")
    a = show / "001 - A"
    (a / "drums.wav").write_bytes(c.read_bytes())
    (a / "lyrics.json").write_text("{}")
    (a / "key.txt").write_text("G\n")
    numbering.reorder(show, [str(c), "001 - A"])  # B, not given, goes after
    assert names(show) == ["001 - C/001 - C.opus", "002 - A/002 - A.opus", "002 - A/drums.wav", "002 - A/key.txt",
                           "002 - A/lyrics.json", "003 - B/003 - B.opus"]
    numbering.reorder(show, ["001 - C.opus"])
    assert names(show)[:2] == ["001 - C/001 - C.opus", "002 - A/002 - A.opus"]


def test_reorder_numbers_the_unnumbered_too(tmp_path):
    folder = tmp_path / "Mine"
    song(folder, "Zeta.mp3")
    song(folder, "Alpha.mp3")
    numbering.reorder(folder, ["Zeta"])
    assert names(folder) == ["001 - Zeta/001 - Zeta.mp3", "002 - Alpha/002 - Alpha.mp3"]


@pytest.mark.parametrize("which", ["nope.opus", "/elsewhere/001 - A/001 - A.opus"])
def test_reorder_refuses(show, which):
    with pytest.raises(SystemExit):
        numbering.reorder(show, [which])
    assert names(show) == ["001 - A/001 - A.opus", "002 - B/002 - B.opus"]
