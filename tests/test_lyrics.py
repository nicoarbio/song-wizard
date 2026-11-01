"""Lyrics: looked up (never on the network in tests), pasted, marked, exported, and following the song."""

import json

import pytest

import synth
from test_ui import TOKEN, get_json, request, server  # noqa: F401  (the fixture)

from song_wizard import delete, lyrics, rename

RESULTS = [
    {"id": 1, "trackName": "Song", "artistName": "Band", "duration": 400.0, "plainLyrics": "far\nversion", "syncedLyrics": None},
    {"id": 2, "trackName": "Song", "artistName": "Band", "duration": 61.0, "plainLyrics": "first line\nsecond line",
     "syncedLyrics": "[00:01.50] first line\n[00:03.00] second line"},
    {"id": 3, "trackName": "Song", "artistName": "Band", "duration": 59.0, "plainLyrics": None, "syncedLyrics": None},
]


@pytest.fixture
def database(monkeypatch):
    asked = []

    def get(url):
        asked.append(url)
        return RESULTS
    monkeypatch.setattr(lyrics, "get", get)
    return asked


@pytest.fixture
def song(tmp_path):
    path = tmp_path / "001 - Band - Song (Official Video).wav"
    synth.write(path, synth.sine(440, 60.0))
    return path


def test_search_picks_the_closest_length(database):
    found = lyrics.search("Song", "Band", 60)
    assert found["text"] == "first line\nsecond line" and found["synced"] == [[1.5, "first line"], [3.0, "second line"]]
    assert "#2" in found["source"] and "track_name=Song" in database[0] and "artist_name=Band" in database[0]


def test_search_without_artist(database):
    lyrics.search("Song", "", None)
    assert "q=Song" in database[0]


def test_parse_lrc():
    assert lyrics.parse_lrc("[ar: x]\n[01:02.25]hola\n[00:00.00] ") == [[62.25, "hola"], [0.0, ""]]
    assert lyrics.parse_lrc("") is None


@pytest.mark.parametrize("bad", [
    {"text": 3},
    {"text": "a\nbc", "marks": [{"line": 5, "from": 0, "to": 1, "color": "yellow"}]},
    {"text": "a\nbc", "marks": [{"line": 1, "from": 0, "to": 3, "color": "yellow"}]},
    {"text": "a\nbc", "marks": [{"line": 1, "from": 0, "to": 1, "color": "black"}]},
    {"text": "a", "notes": {"4": "x"}},
    {"text": "a\nb", "times": {"2": 1.0}},
    {"text": "a\nb", "times": {"1": -3}},
    {"text": "a\nb", "times": {"1": "soon"}},
])
def test_clean_rejects(bad):
    with pytest.raises((ValueError, KeyError, TypeError)):
        lyrics.clean(bad)


def test_fetch_save_and_keep(song, database, capsys):
    lyrics.run([str(song)])
    saved = lyrics.load(song)
    assert saved["text"].startswith("first line") and lyrics.path_for(song).name == "001 - Band - Song (Official Video).lyrics.json"
    assert "found" in capsys.readouterr().out
    # Already there: not looked up again (marks and notes would be lost)...
    database.clear()
    lyrics.run([str(song)])
    assert not database and "has lyrics" in capsys.readouterr().out
    # ...unless forced.
    lyrics.run([str(song)], force=True)
    assert database


def test_times_kept_and_rounded():
    data = lyrics.clean({"text": "a\nb\nc", "times": {"0": 1.234567, "2": 75}})
    assert data["times"] == {"0": 1.23, "2": 75.0}


def test_from_a_file_keeps_marks_on_the_same_text(song, tmp_path):
    text = tmp_path / "letra.txt"
    text.write_text("uno\ndos")
    lyrics.run([str(song)], text_from=str(text))
    lyrics.save(song, {**lyrics.load(song), "marks": [{"line": 1, "from": 0, "to": 3, "color": "pink"}], "notes": {"0": "entra el bajo"},
                       "times": {"1": 12.5}})
    lyrics.run([str(song)], text_from=str(text))
    assert lyrics.load(song)["marks"] and lyrics.load(song)["notes"] == {"0": "entra el bajo"}
    assert lyrics.load(song)["times"] == {"1": 12.5}
    text.write_text("otra letra")
    lyrics.run([str(song)], text_from=str(text))
    assert lyrics.load(song)["marks"] == [] and lyrics.load(song)["notes"] == {} and lyrics.load(song)["times"] == {}


def test_not_found_and_offline(song, monkeypatch, capsys):
    monkeypatch.setattr(lyrics, "get", lambda url: [])
    lyrics.run([str(song)])
    assert "not found" in capsys.readouterr().out and not lyrics.load(song)

    def offline(url):
        raise lyrics.urllib.error.URLError("no network")
    monkeypatch.setattr(lyrics, "get", offline)
    with pytest.raises(SystemExit):
        lyrics.run([str(song)])


def test_export(song):
    lyrics.save(song, {"text": "hola <b>mundo</b>\nchau", "marks": [{"line": 0, "from": 0, "to": 4, "color": "yellow"}],
                       "notes": {"1": "corte"}, "legend": {"yellow": "Voz 1"}})
    lyrics.run([str(song)], export_page=True)
    page = (song.parent / "001 - Band - Song (Official Video).lyrics.html").read_text()
    assert '<mark style="background:#ffe066">hola</mark>' in page and "&lt;b&gt;mundo" in page
    assert "corte" in page and "Voz 1" in page and "<title>Letra: Song (Band)</title>" in page


def test_runs():
    assert lyrics.runs("abcdef", [{"from": 1, "to": 3, "color": "green"}, {"from": 2, "to": 4, "color": "pink"}]) == \
        [("a", None), ("b", "green"), ("cd", "pink"), ("ef", None)]


def test_follows_rename_and_delete(song, monkeypatch):
    lyrics.save(song, {"text": "x"})
    lyrics.export(song)
    rename.run(str(song), "Other")
    folder = song.parent
    assert (folder / "001 - Other.lyrics.json").exists() and (folder / "001 - Other.lyrics.html").exists()
    trashed = []
    monkeypatch.setattr(delete.system, "trash", lambda paths: trashed.extend(paths))
    delete.run(songs=[str(folder / "001 - Other.wav")], yes=True)
    assert {p.rsplit("/", 1)[1] for p in trashed} == {"001 - Other.wav", "001 - Other.lyrics.json", "001 - Other.lyrics.html"}


def test_interface(server, database):  # noqa: F811
    port, root = server
    synth.write(root / "001 - Band - Song.wav", synth.sine(440, 60.0))
    path = "001 - Band - Song.wav"
    got = get_json(port, f"/api/lyrics?path={path.replace(' ', '%20')}")
    assert got["lyrics"] is None and got["title"] == "Song" and len(got["colors"]) == 5
    assert not get_json(port, "/api/library")["folders"][0]["songs"][0]["lyrics"]
    response, content = request(port, "POST", "/api/lyrics/fetch", {"path": path})
    assert response.status == 200 and json.loads(content)["text"].startswith("first line")
    assert get_json(port, "/api/library")["folders"][0]["songs"][0]["lyrics"]
    data = {**json.loads(content), "marks": [{"line": 0, "from": 0, "to": 5, "color": "blue"}], "legend": {"blue": "coro"}}
    assert request(port, "POST", "/api/lyrics", {"path": path, "lyrics": data})[0].status == 200
    assert lyrics.load(root / path)["legend"] == {"blue": "coro"}
    bad = {**data, "marks": [{"line": 0, "from": 0, "to": 99, "color": "blue"}]}
    assert request(port, "POST", "/api/lyrics", {"path": path, "lyrics": bad})[0].status == 400
    response, content = request(port, "GET", f"/lyrics?path={path.replace(' ', '%20')}&t={TOKEN}", token=None)
    assert response.status == 200 and b"#a5d8ff" in content and b"coro" in content
    assert request(port, "GET", f"/lyrics?path={path.replace(' ', '%20')}", token=None)[0].status == 403
    assert request(port, "POST", "/api/lyrics", {"path": "../x.wav", "lyrics": data})[0].status == 403


def test_interface_not_found_and_offline(server, monkeypatch):  # noqa: F811
    port, root = server
    synth.write(root / "Song.wav", synth.sine(440, 1.0))
    monkeypatch.setattr(lyrics, "get", lambda url: [])
    assert request(port, "POST", "/api/lyrics/fetch", {"path": "Song.wav"})[0].status == 404

    def offline(url):
        raise lyrics.urllib.error.URLError("no network")
    monkeypatch.setattr(lyrics, "get", offline)
    response, content = request(port, "POST", "/api/lyrics/fetch", {"path": "Song.wav"})
    assert response.status == 502 and "internet" in json.loads(content)["error"]
