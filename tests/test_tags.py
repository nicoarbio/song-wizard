"""A song's data (tags): read and written in every format, carried to its stems and versions,
renaming by artist and title, downloads named by it, and the library's filter."""

import json
import subprocess

import pytest

from song_wizard import cli, config, download, listing, tags
from synth import sine, write

from test_ui import get_json, request, server, wait_for  # noqa: F401 (fixture)


def opus(path, **fields):
    """A short .opus with these fields, as a download leaves it."""
    command = ["ffmpeg", "-nostdin", "-v", "error", "-y", "-f", "lavfi", "-i", "sine=d=0.5", "-c:a", "libopus"]
    for k, v in fields.items():
        command += ["-metadata", f"{k}={v}"]
    subprocess.run([*command, str(path)], check=True)
    return path


@pytest.fixture
def song(tmp_path):
    folder = tmp_path / "Show"
    folder.mkdir()
    main = opus(folder / "001 - Someone - Song (HQ).opus", title="Song (HQ)", artist="Uploader", genre="Music",
                purl="https://example.com/watch?v=1", synopsis="Line one\nLine two")
    write(folder / "001 - Someone - Song (HQ) (drums).wav", sine(220, 0.3))
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", str(main), str(folder / "001 - Someone - Song (HQ) (80%).mp3")], check=True)
    write(folder / "001 - Someone - Song (HQ) (record 2026-01-03 20-15-00).wav", sine(330, 0.3))
    return main


def names(folder):
    return sorted(p.name for p in folder.iterdir())


def test_read(song):
    data = tags.read(song)
    assert data["title"] == "Song (HQ)" and data["artist"] == "Uploader" and data["synopsis"] == "Line one\nLine two"
    assert tags.read(song.parent / "nope.opus") == {}
    (song.parent / "junk.opus").write_bytes(b"x")
    assert tags.read(song.parent / "junk.opus") == {}


def test_set_everywhere_but_takes(song):
    tags.run(song, ["album=Live", "Mi campo=hola", "genre=Rock"], ["synopsis"])
    for name in ["001 - Someone - Song (HQ).opus", "001 - Someone - Song (HQ) (drums).wav", "001 - Someone - Song (HQ) (80%).mp3"]:
        data = tags.read(song.parent / name)
        assert (data["album"], data["Mi campo"], data["genre"], data["artist"]) == ("Live", "hola", "Rock", "Uploader"), name
        assert "synopsis" not in data and data["purl"] == "https://example.com/watch?v=1", name
    assert "album" not in tags.read(song.parent / "001 - Someone - Song (HQ) (record 2026-01-03 20-15-00).wav")
    # The audio is the same: only the data changed.
    assert subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(song)],
                          capture_output=True, text=True).stdout.strip().startswith("0.5")


def test_new_artist_or_title_renames_all(song, capsys):
    tags.run(song, ["artist=Someone", "title=Song: live?"])
    assert names(song.parent) == ["001 - Someone - Song： live？ (80%).mp3", "001 - Someone - Song： live？ (drums).wav",
                                  "001 - Someone - Song： live？ (record 2026-01-03 20-15-00).wav", "001 - Someone - Song： live？.opus"]
    assert tags.read(song.parent / "001 - Someone - Song： live？.opus")["title"] == "Song: live?"


def test_other_data_doesnt_rename(song):
    tags.run(song, ["genre=Rock"])
    assert "001 - Someone - Song (HQ).opus" in names(song.parent)


def test_only_one_file(song):
    version = song.parent / "001 - Someone - Song (HQ) (80%).mp3"
    tags.run(version, ["comment=the show's version", "title=Other"], only=True)
    assert tags.read(version)["comment"] == "the show's version"
    assert "comment" not in tags.read(song) or tags.read(song)["comment"] != "the show's version"
    assert "001 - Someone - Song (HQ) (80%).mp3" in names(song.parent)  # --only never renames


def test_purl_stays(song):
    with pytest.raises(SystemExit):
        tags.run(song, unset=["purl"])
    with pytest.raises(SystemExit):
        tags.run(song, ["no value"])


def test_show(song, capsys):
    cli.main(["tag", str(song)])
    out = capsys.readouterr().out
    assert "  title: Song (HQ)" in out and "  synopsis: Line one\n" in out


def test_name_for():
    assert tags.name_for({"title": "Song", "artist": "Band"}) == "Band - Song"
    assert tags.name_for({"title": " Song.  "}) == "Song"
    assert tags.name_for({"artist": "Band"}) is None
    assert tags.name_for({"title": 'a/b:c*d?"e<f>g|h\\i'}) == "a⧸b：c＊d？＂e＜f＞g｜h⧹i"


def test_title_artist(song):
    assert tags.title_artist(song) == ("Song", "Uploader")  # "(HQ)" off, as on a setlist
    plain = song.parent / "002 - Band - Other (Official Video).wav"
    write(plain, sine(220, 0.2))
    assert tags.title_artist(plain) == ("Other", "Band")  # no data: from the name


def test_matches():
    assert tags.matches("cancion ROCK", "001 - Banda - Canción.opus", "Show", "Rock")
    assert tags.matches("rock banda", "001 - Banda - Canción.opus", "Show", "Rock")
    assert not tags.matches("jazz", "001 - Banda - Canción.opus", "Show", "Rock")
    assert tags.matches("", "anything")


def test_list_filters_by_words_and_data(song, monkeypatch, capsys):
    monkeypatch.setenv("SONG_WIZARD_DIR", str(song.parent.parent))
    tags.run(song, ["album=Último show"])
    capsys.readouterr()
    listing.run("ultimo SONG")
    assert "001 - Someone - Song (HQ).opus" in capsys.readouterr().out
    listing.run("ultimo jazz")
    assert "Nothing found." in capsys.readouterr().out


def test_download_names_by_data(song, monkeypatch, capsys):
    download.name_by_data(str(song))
    assert "001 - Uploader - Song (HQ).opus" in names(song.parent)
    assert "001 - Uploader - Song (HQ) (drums).wav" in names(song.parent)
    download.name_by_data(str(song.parent / "001 - Uploader - Song (HQ).opus"))  # already so: nothing to do
    loose = opus(song.parent / "Clip.opus")
    download.name_by_data(str(loose))  # no data: keeps its name
    assert "Clip.opus" in names(song.parent)


def test_config_written_by_any_command(tmp_path, capsys):
    assert not config.CONFIG_PATH.exists()
    cli.main(["tag", str(opus(tmp_path / "a.opus"))])
    assert config.CONFIG_PATH.read_text() == config.TEMPLATE
    assert not config.ensure()


def test_interface(server, monkeypatch):
    port, root = server
    main = opus(root / "001 - A - B.opus", title="B", artist="A")
    write(root / "001 - A - B (drums).wav", sine(220, 0.2))
    data = get_json(port, f"/api/tags?path={main.name.replace(' ', '%20')}")
    assert data["tags"]["artist"] == "A" and data["files"] == ["001 - A - B (drums).wav", "001 - A - B.opus"]
    (folder,) = get_json(port, "/api/library")["folders"]
    assert folder["songs"][0]["tags"] == {"title": "B", "artist": "A"}
    response, content = request(port, "POST", "/api/jobs", {"action": "tag", "paths": [main.name],
                                                             "set": {"artist": "C", "album": "D"}, "unset": ["genre"]})
    job = json.loads(content)
    assert job["title"] == "Datos: 001 - A - B.opus"
    status, lines = wait_for(port, job["id"])
    assert status == "done", lines
    (folder,) = get_json(port, "/api/library")["folders"]
    assert folder["songs"][0]["name"] == "001 - C - B.opus" and folder["songs"][0]["tags"]["album"] == "D"
    for bad in [{"set": {"a=b": "x"}}, {"set": {}, "unset": []}, {"set": {"x": "y"}, "paths": ["001 - C - B.opus", "001 - C - B (drums).wav"]}]:
        body = {"action": "tag", "paths": ["001 - C - B.opus"], **bad}
        assert request(port, "POST", "/api/jobs", body)[0].status == 400, bad
