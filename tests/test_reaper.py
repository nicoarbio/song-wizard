"""The REAPER project of a song: what goes in, the timing, never rewriting an existing one, the
takes' names in REAPER's settings, and following the song when it's renamed or deleted. (Loading
it in REAPER itself was checked by hand: see CHECKLIST.md.)"""

import json
import re

import pytest

import synth
from test_ui import get_json, request, server  # noqa: F401  (the fixture)

from song_wizard import align, delete, reaper, rename, results
from song_wizard.audio import base_of

SONG = '001 - Band "Live" & Co'


def make_song(folder, stems=(), seconds=3.0, name=SONG):
    folder.mkdir(parents=True, exist_ok=True)
    song = synth.write(folder / f"{name}.wav", synth.sine(220, seconds))
    for s in stems:
        synth.write(folder / f"{name} ({s}).wav", synth.sine(330, seconds))
    return song


def blocks(text):
    """The NAME, MUTESOLO, REC, POSITION and FILE of each TRACK in the project."""
    found = []
    for chunk in text.split("  <TRACK ")[1:]:
        get = lambda key: (re.search(rf"^\s*{key} (.*)$", chunk, re.M) or [None, None])[1]
        found.append({k: get(k) for k in ("NAME", "MUTESOLO", "REC", "POSITION", "FILE")})
    return found


def test_tracks_every_stem(tmp_path):
    song = make_song(tmp_path, ["vocals", "drums", "bass", "guitar", "other", "no drums"])
    tracks = reaper.tracks_for(song)
    assert [(n, m) for n, _, m in tracks] == [("Voz", False), ("Batería", False), ("Bajo", False), ("Guitarra", False),
                                              ("Otros", False), ("Sin batería", True), ("Tema original", True)]
    assert tracks[1][1] == f"{SONG} (drums).wav"


def test_tracks_one_instrument_or_none(tmp_path):
    song = make_song(tmp_path / "a", ["drums", "no drums"])
    assert [(n, m) for n, _, m in reaper.tracks_for(song)] == [("Batería", False), ("Sin batería", False), ("Tema original", True)]
    song = make_song(tmp_path / "b")
    assert reaper.tracks_for(song) == [("Tema original", f"{SONG}.wav", False)]


def test_build_lines_up_the_first_beat(tmp_path):
    song = make_song(tmp_path, ["drums", "no drums"])
    results.save("click", [(str(song), align.describe(123.4, "4/4", 0.5))])
    text, problem = reaper.build(song)
    assert problem is None
    assert "  TEMPO 123.4 4 4 0" in text and '  RECORD_PATH "" ""' in text
    tracks = blocks(text)
    bar = 4 * 60 / 123.4
    # The audio starts where its first beat (0.5 s in) lands on the bar line after it.
    assert float(tracks[0]["POSITION"]) == pytest.approx(bar - 0.5)
    # Names with double quotes go in single quotes: REAPER has no escaping.
    assert tracks[0]["FILE"] == f"'{SONG} (drums).wav'"
    assert [t["NAME"] for t in tracks] == ['"Batería"', '"Sin batería"', '"Tema original"', '"Click"', '"Grabación"']
    assert "BPM 123.4" in text and "PATTERNSTR ABBB" in text
    # Armed to record from inputs 1/2, monitoring off; every track at 0 dB.
    assert tracks[-1]["REC"] == "1 1024 0 0 0 0 0 0"
    assert set(re.findall(r"^    VOLPAN (.*)$", text, re.M)) == {"1 0 -1 -1 1"}


def test_build_without_click(tmp_path):
    song = make_song(tmp_path)
    results.save("bpm", [(str(song), "98.5 BPM  steady")])
    text, problem = reaper.build(song)
    assert problem == "unaligned" and "  TEMPO 98.5 4 4 0" in text and float(blocks(text)[0]["POSITION"]) == 0
    (tmp_path / "bpm.txt").unlink()
    text, problem = reaper.build(song)
    assert problem == "no-tempo" and "  TEMPO 120 4 4 0" in text


def test_make_never_rewrites(tmp_path, monkeypatch):
    song = make_song(tmp_path, ["drums", "no drums"])
    project, created, info = reaper.make(tmp_path / f"{SONG} (drums).wav")  # a stem finds its song
    assert created and project.name == f"{SONG}.rpp" and info["timing"] == "no-tempo"
    project.write_text("edited in REAPER")
    again, created, _ = reaper.make(song)
    assert again == project and not created and project.read_text() == "edited in REAPER"
    trashed = []
    monkeypatch.setattr(reaper.system, "trash", lambda paths: [trashed.extend(paths), project.unlink()])
    _, created, info = reaper.make(song, redo=True)
    assert created and info["trashed"] and trashed == [str(project)] and project.read_text().startswith("<REAPER_PROJECT")


def test_run_without_reaper(tmp_path, capsys, monkeypatch):
    song = make_song(tmp_path)
    opened = []
    monkeypatch.setattr(reaper.system, "launch", opened.append)
    reaper.run(str(song))
    out = capsys.readouterr().out
    assert "Created" in out and "doesn't seem to be installed" in out and not opened


def test_take_names(tmp_path, monkeypatch):
    ini = tmp_path / "reaper.ini"
    assert reaper.take_names(ini) is None  # REAPER never ran: nothing to change
    ini.write_bytes(b"[reaper]\r\nmultinst=0\r\n[audioconfig]\r\nmode=2\r\n")
    monkeypatch.setattr(reaper, "running", lambda: True)
    assert reaper.take_names(ini) == "running" and b"recfile" not in ini.read_bytes()
    monkeypatch.setattr(reaper, "running", lambda: False)
    assert reaper.take_names(ini) == "set"
    assert ini.read_bytes() == f"[reaper]\r\nrecfile_wildcards={reaper.TAKES}\r\nmultinst=0\r\n[audioconfig]\r\nmode=2\r\n".encode()
    assert (tmp_path / reaper.BACKUP).read_bytes() == b"[reaper]\r\nmultinst=0\r\n[audioconfig]\r\nmode=2\r\n"
    assert reaper.take_names(ini) is None
    ini.write_text("[reaper]\nrecfile_wildcards=$tracknumber-$track\n")
    assert reaper.take_names(ini) == "set" and ini.read_text() == f"[reaper]\nrecfile_wildcards={reaper.TAKES}\n"
    # The first backup is kept: it has the settings from before song-wizard.
    assert b"multinst" in (tmp_path / reaper.BACKUP).read_bytes()


def test_takes_go_with_their_song():
    assert base_of(f"{SONG} (record 2026-11-01 19-05-12).wav") == SONG
    assert base_of(f"{SONG} (record 2026-11-01 19-05-12)-001.wav") == SONG


def test_follows_rename_and_delete(tmp_path, monkeypatch):
    song = make_song(tmp_path, ["drums", "no drums"])
    project, _, _ = reaper.make(song)
    take = synth.write(tmp_path / f"{SONG} (record 2026-11-01 19-05-12).wav", synth.sine(440, 1.0))
    (tmp_path / f"{SONG} (drums).wav.reapeaks").write_bytes(b"peaks")
    (tmp_path / f"{SONG}.rpp-bak").write_text(project.read_text())
    project.write_text(project.read_text() + f'      FILE "{take.name}"\n')
    rename.run(str(song), "New")
    new = tmp_path / "001 - New.rpp"
    text = new.read_text()
    assert "FILE '001 - New (drums).wav'" in text and 'FILE "001 - New (record 2026-11-01 19-05-12).wav"' in text
    assert SONG not in text and SONG not in (tmp_path / "001 - New.rpp-bak").read_text()
    assert (tmp_path / "001 - New (drums).wav.reapeaks").exists()
    trashed = []
    monkeypatch.setattr(delete.system, "trash", lambda paths: trashed.extend(paths))
    delete.run(songs=[str(tmp_path / "001 - New.wav")], yes=True)
    assert {p.rsplit("/", 1)[1] for p in trashed} >= {"001 - New.rpp", "001 - New.rpp-bak", "001 - New (drums).wav.reapeaks",
                                                      "001 - New (record 2026-11-01 19-05-12).wav"}


def test_interface(server, monkeypatch):  # noqa: F811
    port, root = server
    make_song(root, name="001 - Song")
    library = get_json(port, "/api/library")
    assert library["reaper"] is False and library["folders"][0]["songs"][0]["reaper"] is False
    response, content = request(port, "POST", "/api/reaper", {"path": "001 - Song.wav"})
    got = json.loads(content)
    assert response.status == 200 and got["created"] and not got["opened"] and got["name"] == "001 - Song.rpp"
    assert get_json(port, "/api/library")["folders"][0]["songs"][0]["reaper"] is True
    opened = []
    monkeypatch.setattr(reaper, "installed", lambda: True)
    monkeypatch.setattr(reaper, "open_project", opened.append)
    got = json.loads(request(port, "POST", "/api/reaper", {"path": "001 - Song.wav"})[1])
    assert not got["created"] and opened == [root / "001 - Song.rpp"]
    assert request(port, "POST", "/api/reaper", {"path": "../x.wav"})[0].status == 403
    assert request(port, "POST", "/api/reaper", {"path": "nope.wav"})[0].status == 404


def test_restore_and_apply(tmp_path, monkeypatch, capsys):
    ini = reaper.ini_path()
    ini.parent.mkdir(parents=True)
    ini.write_bytes(b"[reaper]\r\nrecfile_wildcards=$track-$year\r\nmultinst=0\r\n")
    assert reaper.setting()["changed"] is None and reaper.restore() == "not-changed"
    assert reaper.take_names() == "set"
    now = reaper.setting()
    assert now["ours"] and now["before"] == "$track-$year" and now["changed"] and now["backup"]
    reaper.run_setting("show")
    assert "before, it was: $track-$year" in capsys.readouterr().out
    monkeypatch.setattr(reaper, "running", lambda: True)
    assert reaper.restore() == "running" and reaper.setting()["ours"]
    monkeypatch.setattr(reaper, "running", lambda: False)
    ini.write_bytes(ini.read_bytes() + b"[other]\r\nadded_later=1\r\n")  # changed in REAPER since
    assert reaper.restore() == "restored"
    assert ini.read_bytes() == b"[reaper]\r\nrecfile_wildcards=$track-$year\r\nmultinst=0\r\n[other]\r\nadded_later=1\r\n"
    # Put back by the user: making projects doesn't change it again...
    assert reaper.take_names() is None and reaper.setting()["declined"]
    # ...until asked to.
    assert reaper.apply() == "set" and reaper.setting()["ours"] and not reaper.setting()["declined"]


def test_restore_to_default(tmp_path):
    ini = reaper.ini_path()
    ini.parent.mkdir(parents=True)
    ini.write_text("[reaper]\nmultinst=0\n")
    reaper.take_names()
    assert reaper.setting()["before"] is None and reaper.restore() == "restored"
    assert ini.read_text() == "[reaper]\nmultinst=0\n"


def test_changed_before_the_record(tmp_path):
    """Changed by a version that didn't keep a record: the copy it made says how it was."""
    ini = reaper.ini_path()
    ini.parent.mkdir(parents=True)
    ini.with_name(reaper.BACKUP).write_text("[reaper]\nmultinst=0\n")
    ini.write_text(f"[reaper]\nrecfile_wildcards={reaper.TAKES}\nmultinst=0\n")
    now = reaper.setting()
    assert now["changed"] and now["before"] is None
    assert reaper.restore() == "restored" and ini.read_text() == "[reaper]\nmultinst=0\n"


def test_interface_setting(server, monkeypatch):  # noqa: F811
    port, root = server
    ini = reaper.ini_path()
    ini.parent.mkdir(parents=True)
    ini.write_text("[reaper]\n")
    got = get_json(port, "/api/reaper/setting")
    assert got["exists"] and not got["ours"] and not got["installed"]
    make_song(root, name="001 - Song")
    monkeypatch.setattr(reaper, "installed", lambda: True)
    monkeypatch.setattr(reaper, "open_project", lambda p: True)
    got = json.loads(request(port, "POST", "/api/reaper", {"path": "001 - Song.wav"})[1])
    assert got["takes"] == "set" and got["setting"]["ours"] and got["setting"]["before"] is None
    got = json.loads(request(port, "POST", "/api/reaper/setting", {"do": "restore"})[1])
    assert got["done"] == "restored" and got["declined"] and not got["ours"]
    got = json.loads(request(port, "POST", "/api/reaper/setting", {"do": "apply"})[1])
    assert got["done"] == "set" and got["ours"]
    assert request(port, "POST", "/api/reaper/setting", {"do": "rm -rf"})[0].status == 400


def test_source_type_per_format(tmp_path):
    """With the wrong source type (an .opus as WAVE) REAPER shows the item but it's silent."""
    from song_wizard.audio import AUDIO_EXTS
    assert set(reaper.SOURCES) == AUDIO_EXTS
    assert reaper.source("a.opus")[0] == "<SOURCE OPUS" and reaper.source("b.WAV")[0] == "<SOURCE WAVE"
    folder = tmp_path / "s"
    folder.mkdir()
    import subprocess
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "sine=f=220:d=2", "-c:a", "libopus",
                    str(folder / "001 - Song.opus")], check=True)
    synth.write(folder / "001 - Song (drums).wav", synth.sine(330, 2.0))
    synth.write(folder / "001 - Song (no drums).wav", synth.sine(330, 2.0))
    text, _ = reaper.build(folder / "001 - Song.opus")
    assert text.count("<SOURCE WAVE") == 2 and re.search(r'<SOURCE OPUS\n\s*FILE "001 - Song.opus"', text)
