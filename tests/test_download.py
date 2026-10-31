"""download, with yt-dlp replaced by a fake: no network."""

from pathlib import Path

import pytest

from song_wizard import archives, download


def fake_ytdlp(monkeypatch, songs, title="Show"):
    calls = []

    class Done:
        returncode = 0

    def run(args):
        calls.append(args)
        prints = {args[i + 1]: args[i + 2] for i, a in enumerate(args) if a == "--print-to-file"}
        Path(prints["playlist:%(title)s"]).write_text(title + "\n")
        Path(prints["after_move:%(filepath)s"]).write_text("".join(f"{s}\n" for s in songs))
        archive = Path(args[args.index("--download-archive") + 1])
        archive.write_text("youtube id1\n")
        return Done()

    monkeypatch.setattr(download.subprocess, "run", run)
    monkeypatch.setattr(download, "node_ok", lambda: False)
    return calls


def test_download_remembers_folder(monkeypatch, tmp_path):
    monkeypatch.setenv("SONG_WIZARD_DIR", str(tmp_path))
    calls = fake_ytdlp(monkeypatch, [f"{tmp_path}/Show/001 - A.opus", f"{tmp_path}/Show/002 - B.opus"])
    with pytest.raises(SystemExit) as e:
        download.run("https://www.youtube.com/playlist?list=PLx", wav=True)
    assert e.value.code == 0
    assert "--exec" in calls[0]
    (playlist,) = archives.playlists()
    assert playlist == {"id": "PLx", "title": "Show", "url": "https://www.youtube.com/playlist?list=PLx",
                        "folder": str(tmp_path / "Show"), "wav": True}
    assert archives.playlist_for(tmp_path / "Show")["id"] == "PLx"


def test_nothing_new_keeps_folder(monkeypatch, tmp_path):
    monkeypatch.setenv("SONG_WIZARD_DIR", str(tmp_path))
    fake_ytdlp(monkeypatch, [f"{tmp_path}/Show/001 - A.opus"])
    with pytest.raises(SystemExit):
        download.run("https://www.youtube.com/playlist?list=PLx")
    fake_ytdlp(monkeypatch, [])  # second run: everything already downloaded
    with pytest.raises(SystemExit):
        download.run("https://www.youtube.com/playlist?list=PLx")
    assert archives.playlists()[0]["folder"] == str(tmp_path / "Show")
