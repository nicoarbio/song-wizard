"""Going over a playlist before downloading it: songs that left it go to Singles (no gaps left),
and what to do with its songs already here elsewhere is asked first. yt-dlp is faked."""

import subprocess
from pathlib import Path

import pytest

from song_wizard import archives, download, review, tags

URL = "https://www.youtube.com/playlist?list=PLx"
OTHER = "https://www.youtube.com/playlist?list=PLo"


def tone(path, vid=None):
    """A short song as a download leaves it: in its folder, with its link."""
    path.parent.mkdir(parents=True, exist_ok=True)
    command = ["ffmpeg", "-nostdin", "-v", "error", "-y", "-f", "lavfi", "-i", "sine=d=0.2", "-c:a", "libopus"]
    if vid:
        command += ["-metadata", f"purl=https://www.youtube.com/watch?v={vid}"]
    subprocess.run([*command, str(path)], check=True)
    return path


def song(container, name, vid=None, extra=()):
    here = container / name
    main = tone(here / f"{name}.opus", vid)
    for f in extra:
        (here / f).write_text(f)
    return main


def files(folder):
    return sorted(str(p.relative_to(folder)) for p in folder.rglob("*") if p.is_file() and not p.name.startswith("."))


@pytest.fixture
def library(tmp_path, monkeypatch):
    """Show (a playlist: a1, b1, c1), Other (a playlist: o1) and Singles (s1, and one added by hand)."""
    music = tmp_path / "music"
    monkeypatch.setenv("SONG_WIZARD_DIR", str(music))
    show, other, singles = music / "Show", music / "Other", music / "Singles"
    song(show, "001 - Band - A", "aaaaaaaaaa1", ["drums.opus", "key.txt"])
    song(show, "002 - Band - B", "bbbbbbbbbb1", ["drums.opus", "lyrics.json"])
    song(show, "003 - Band - C", "cccccccccc1")
    song(show, "004 - Mine", None)  # added by hand: no link
    song(other, "001 - Band - O", "oooooooooo1", ["bass.opus"])
    song(singles, "Band - S", "ssssssssss1", ["drums.opus", "tempo.txt"])
    song(singles, "Recorded", None)
    archives.ARCHIVE_DIR.mkdir(parents=True)
    (archives.ARCHIVE_DIR / "PLx.txt").write_text("youtube aaaaaaaaaa1\nyoutube bbbbbbbbbb1\nyoutube cccccccccc1\n")
    (archives.ARCHIVE_DIR / "PLo.txt").write_text("youtube oooooooooo1\n")
    (archives.ARCHIVE_DIR / "singles.txt").write_text("youtube ssssssssss1\n")
    archives.remember("PLx", URL, "Show", folder=str(show))
    archives.remember("PLo", OTHER, "Other", folder=str(other))
    archives.remember(archives.SINGLES, None, None, folder=str(singles))
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    return music


def fake_ytdlp(monkeypatch, remote, count=None, title="Show"):
    """yt-dlp: the playlist lists `remote` ([(id, title)]); downloading makes nothing, but says
    which ids it would have downloaded (those not in its archive)."""
    got = {"downloaded": None}
    real = subprocess.run

    def run(args, **kw):
        if "yt_dlp" not in args:  # ffmpeg
            return real(args, **kw)
        output = args[args.index("-o") + 1].replace("%%", "%")
        if "--flat-playlist" in args:
            n = count if count is not None else len(remote)
            folder = output.split("/%(playlist_title|Singles)s/")[0] + f"/{title}" if "%(playlist_title" in output \
                else str(Path(output).parent)
            lines = []
            for i, (vid, name) in enumerate(remote, 1):
                lines += [f"{vid}\t{n}\t{name}", f"{folder}/{i:03d} - {name}.NA"]
            return subprocess.CompletedProcess(args, 0, "\n".join(lines) + "\n", "")
        archive = Path(args[args.index("--download-archive") + 1])
        have = archive.read_text().split() if archive.exists() else []
        got["downloaded"] = [vid for vid, _ in remote if vid not in have]
        return subprocess.CompletedProcess(args, 0)

    monkeypatch.setattr(download.subprocess, "run", run)
    monkeypatch.setattr(review.subprocess, "run", run)
    monkeypatch.setattr(download, "node_ok", lambda: False)
    return got


def test_left_the_playlist_goes_to_singles_without_gaps(library, monkeypatch, capsys):
    show, singles = library / "Show", library / "Singles"
    got = fake_ytdlp(monkeypatch, [("aaaaaaaaaa1", "A"), ("cccccccccc1", "C")])
    assert download.fetch(URL) == 0
    assert "not in the playlist anymore" in capsys.readouterr().out
    # B went to Singles with everything it had, without its number; C and the one added by hand moved up.
    assert sorted(p.name for p in show.iterdir() if p.is_dir()) == ["001 - Band - A", "002 - Band - C", "003 - Mine"]
    assert files(singles / "Band - B") == ["Band - B.opus", "drums.opus", "lyrics.json"]
    assert "youtube bbbbbbbbbb1" not in (archives.ARCHIVE_DIR / "PLx.txt").read_text()
    assert "youtube bbbbbbbbbb1" in (archives.ARCHIVE_DIR / "singles.txt").read_text()
    assert got["downloaded"] == []


def test_nothing_moves_if_the_list_came_back_incomplete(library, monkeypatch, capsys):
    before = files(library)
    fake_ytdlp(monkeypatch, [("aaaaaaaaaa1", "A")], count=3)
    download.fetch(URL)
    assert files(library) == before


def test_nothing_moves_if_the_list_failed(library, monkeypatch, capsys):
    before = files(library)

    def offline(args, **kw):
        return subprocess.CompletedProcess(args, 1, "", "ERROR: offline")
    monkeypatch.setattr(review.subprocess, "run", offline)
    monkeypatch.setattr(download.subprocess, "run", offline)
    monkeypatch.setattr(download, "node_ok", lambda: False)
    download.fetch(URL)
    assert "Couldn't go over the playlist first" in capsys.readouterr().out
    assert files(library) == before


def test_asks_before_anything_without_a_terminal(library, monkeypatch, capsys):
    before = files(library)
    got = fake_ytdlp(monkeypatch, [("aaaaaaaaaa1", "A"), ("ssssssssss1", "S"), ("oooooooooo1", "O")])
    with pytest.raises(SystemExit) as e:
        download.fetch(URL)
    assert "Band - S" in str(e.value) and "001 - Band - O" in str(e.value) and "ssssssssss1=download|copy|move" in str(e.value)
    assert "oooooooooo1=download|copy)" in str(e.value)  # from another playlist: never moved
    assert files(library) == before and got["downloaded"] is None  # nothing moved, nothing downloaded
    with pytest.raises(SystemExit):
        download.fetch(URL, decide=["ssssssssss1=move", "oooooooooo1=move"])  # not allowed: asked again
    assert files(library) == before


def test_move_copy_and_download_again(library, monkeypatch, capsys):
    show, singles, other = library / "Show", library / "Singles", library / "Other"
    got = fake_ytdlp(monkeypatch, [("aaaaaaaaaa1", "A"), ("bbbbbbbbbb1", "B"), ("cccccccccc1", "C"),
                                   ("ssssssssss1", "S"), ("oooooooooo1", "O"), ("nnnnnnnnnn1", "New")])
    download.fetch(URL, decide=["ssssssssss1=move", "oooooooooo1=copy"])
    out = capsys.readouterr().out
    assert "moved to the playlist as 005 - Band - S" in out and "copied to the playlist as 006 - Band - O" in out
    # At the end, with everything they had (named after the playlist's numbering); the new one is downloaded.
    assert files(show / "005 - Band - S") == ["005 - Band - S.opus", "drums.opus", "tempo.txt"]
    assert files(show / "006 - Band - O") == ["006 - Band - O.opus", "bass.opus"]
    assert got["downloaded"] == ["nnnnnnnnnn1"]
    assert sorted(p.name for p in singles.iterdir() if p.is_dir()) == ["Recorded"]  # moved out of Singles
    assert files(other / "001 - Band - O") == ["001 - Band - O.opus", "bass.opus"]  # still in the other playlist
    record = (archives.ARCHIVE_DIR / "PLx.txt").read_text()
    assert "youtube ssssssssss1" in record and "youtube oooooooooo1" in record
    assert "ssssssssss1" not in (archives.ARCHIVE_DIR / "singles.txt").read_text()
    assert tags.read(show / "005 - Band - S" / "005 - Band - S.opus")["purl"].endswith("ssssssssss1")


def test_download_again(library, monkeypatch):
    (archives.ARCHIVE_DIR / "PLx.txt").write_text((archives.ARCHIVE_DIR / "PLx.txt").read_text() + "youtube oooooooooo1\n")
    got = fake_ytdlp(monkeypatch, [("aaaaaaaaaa1", "A"), ("bbbbbbbbbb1", "B"), ("cccccccccc1", "C"), ("oooooooooo1", "O")])
    download.fetch(URL, decide=["oooooooooo1=download"])
    assert got["downloaded"] == ["oooooooooo1"]  # out of the archive, so yt-dlp gets it
    assert (library / "Other" / "001 - Band - O").is_dir()


def test_asked_in_the_terminal(library, monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    answers = iter(["x", "c"])  # a wrong answer asks again
    monkeypatch.setattr("builtins.input", lambda prompt: next(answers))
    fake_ytdlp(monkeypatch, [("aaaaaaaaaa1", "A"), ("bbbbbbbbbb1", "B"), ("cccccccccc1", "C"), ("ssssssssss1", "S")])
    download.fetch(URL)
    assert (library / "Show" / "005 - Band - S").is_dir() and (library / "Singles" / "Band - S").is_dir()


def test_a_new_playlist_with_a_song_from_singles(library, monkeypatch):
    got = fake_ytdlp(monkeypatch, [("ssssssssss1", "S"), ("nnnnnnnnnn1", "New")], title="Gig")
    download.fetch("https://www.youtube.com/playlist?list=PLg", decide=["ssssssssss1=copy"])
    assert got["downloaded"] == ["nnnnnnnnnn1"]
    assert files(library / "Gig") == ["001 - Band - S/001 - Band - S.opus", "001 - Band - S/drums.opus",
                                      "001 - Band - S/tempo.txt"]
    assert archives.read_meta("PLg")["folder"] == str(library / "Gig")


def test_a_single_link_to_a_song_of_a_playlist(library, monkeypatch):
    fake_ytdlp(monkeypatch, [("oooooooooo1", "O")], title="Singles")  # a single link: no playlist title
    with pytest.raises(SystemExit) as e:
        download.fetch("https://www.youtube.com/watch?v=oooooooooo1")
    assert "oooooooooo1=download|copy" in str(e.value)
    download.fetch("https://www.youtube.com/watch?v=oooooooooo1", decide=["oooooooooo1=copy"])
    assert (library / "Singles" / "Band - O" / "Band - O.opus").is_file()  # Singles: no number
    assert (library / "Other" / "001 - Band - O").is_dir()
