"""tidy: songs from before 0.42.0, loose in their folder, to a folder each, all or nothing, and back."""

import json
import os

import pytest

from song_wizard import align, cli, layout, results, song, ui

A = "006 - Camila - Bésame"
B = "002 - Rascal Flatts - Life Is A Highway"


def files(folder):
    return sorted(str(p.relative_to(folder)) for p in folder.rglob("*") if p.is_file())


@pytest.fixture
def show(tmp_path):
    """A playlist's folder as 0.41 left it (named after the real one this was tried on)."""
    folder = tmp_path / "Show"
    (folder / "peaks").mkdir(parents=True)
    for name in [f"{A}.opus", f"{A} (drums).opus", f"{A} (no drums).opus", f"{A} (drums) (80%).wav",
                 f"{A} (record 2026-11-05 21-30-51).wav", f"{A}.lyrics.json", f"{A}.drums.json", f"{A}.drums.mid",
                 f"{A} (drums).opus.reapeaks", f"{B}.opus", f"{B} (+3).mp3", f"{B} (click 103 BPM 4-4).wav",
                 "Click 120 BPM 4-4.wav", "Cryin chords.pdf"]:
        (folder / name).write_text(name)
    (folder / f"{A}.rpp").write_text(f'<REAPER_PROJECT\n  RECORD_PATH "" ""\n  FILE "{A} (drums).opus"\n'
                                     f'  FILE "{A}.opus"\n  FILE "{A} (record 2026-11-05 21-30-51).wav"\n'
                                     '  FILE "Cryin chords.pdf"\n>\n')
    for name in [f"{A}.opus.reapeaks", f"{A} (no drums).opus.reapeaks", "001 - Gone (bass).wav.reapeaks"]:
        (folder / "peaks" / name).write_text("p")
    (folder / "key.txt").write_text(f"# song-wizard key\n{A}.opus\tAm   A minor  4/4\n{A} (drums).opus\tC\n")
    (folder / "bpm.txt").write_text(f"# song-wizard bpm\n{A}.opus\t98.0 BPM  steady\n{B}.opus\t100.0 BPM  set by hand\n")
    (folder / "click.txt").write_text(f"# song-wizard click\n{A}.opus\t97.50 BPM 4/4, first beat 0.250 s\n"
                                      f"{B}.opus\t103.00 BPM 4/4, first beat -1.153 s\n")
    return folder


def test_needed(show, tmp_path):
    assert layout.needed(show)
    plain = tmp_path / "Plain"
    plain.mkdir()
    (plain / "Song.opus").write_text("x")  # just a file, added by hand: no tidy needed, it's folded
    assert not layout.needed(plain)
    assert layout.fold(plain, settle=0) == [plain / "Song" / "Song.opus"]


def test_tidy(show, capsys):
    before = {f: (show / f).read_bytes() for f in files(show)}
    assert layout.tidy(show) == 2
    assert "2 songs in a folder each" in capsys.readouterr().out
    a, b = show / A, show / B
    assert sorted(os.listdir(a)) == sorted([
        f"{A}.opus", "drums.opus", "no drums.opus", "drums 80%.wav", "record 2026-11-05 21-30-51.wav",
        "lyrics.json", "drums.json", f"{A}.drums.mid", "drums.opus.reapeaks", f"{A}.rpp", "peaks", "key.txt", "tempo.txt"])
    assert (a / "drums 80%.wav").read_text() == f"{A} (drums) (80%).wav"  # the same file, moved
    assert sorted(os.listdir(a / "peaks")) == [f"{A}.opus.reapeaks", "no drums.opus.reapeaks"]
    assert sorted(os.listdir(b)) == sorted([f"{B}.opus", "+3.mp3", "click 103 BPM 4-4.wav", "tempo.txt"])
    # What isn't a song's stays: a click track of no song, the band's PDFs, REAPER's caches of files gone.
    assert sorted(os.listdir(show)) == sorted([".song-wizard-tidy.json", B, A, "Click 120 BPM 4-4.wav", "Cryin chords.pdf", "peaks"])
    assert os.listdir(show / "peaks") == ["001 - Gone (bass).wav.reapeaks"]
    # One key and one tempo per song: the practice click's, set by hand if the tempo was typed in.
    assert results.read(a, "key") == "Am   A minor  4/4"
    assert results.read(a, "tempo") == "97.50 BPM 4/4, first beat 0.250 s"
    assert results.read(b, "tempo") == "103.00 BPM 4/4, first beat -1.153 s  set by hand"
    assert align.grid(b)["bpm"] == 103
    # The REAPER project points to the new names.
    text = (a / f"{A}.rpp").read_text()
    assert 'FILE "drums.opus"' in text and f'FILE "{A}.opus"' in text and 'FILE "record 2026-11-05 21-30-51.wav"' in text
    assert song.kind("record 2026-11-05 21-30-51.wav") == "take" and not layout.needed(show)
    # And back, exactly as it was.
    layout.undo(show)
    assert {f: (show / f).read_bytes() for f in files(show)} == before
    assert not (show / A).exists()


def test_all_or_nothing(show, monkeypatch):
    before = files(show)
    real, calls = os.rename, []

    def flaky(src, dst):
        calls.append(src)
        if len(calls) == 6:
            raise PermissionError("in use")
        real(src, dst)
    monkeypatch.setattr(layout.os, "rename", flaky)
    with pytest.raises(SystemExit):
        layout.tidy(show)
    monkeypatch.setattr(layout.os, "rename", real)
    assert files(show) == before


def test_clash_moves_nothing(show):
    (show / A).mkdir()
    (show / A / "mine.txt").write_text("x")
    before = files(show)
    with pytest.raises(SystemExit):
        layout.tidy(show)
    assert files(show) == before


def test_not_while_reaper_is_open(show, monkeypatch):
    from song_wizard import reaper
    monkeypatch.setattr(reaper, "running", lambda: True)
    with pytest.raises(SystemExit):
        layout.tidy(show)
    assert layout.needed(show)


def test_commands_refuse_the_old_layout(show, capsys):
    with pytest.raises(SystemExit):
        cli.main(["key", str(show)])
    assert "song-wizard tidy" in capsys.readouterr().err
    with pytest.raises(SystemExit):
        cli.main(["bpm", str(show / f"{A}.opus")])


def test_cli_and_a_second_time(show, tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("SONG_WIZARD_DIR", str(tmp_path))
    cli.main(["tidy"])  # every folder of the library that needs it
    assert not layout.needed(show)
    (show / "007 - New.opus").write_text("n")  # copied in the old way later, with a stem
    (show / "007 - New (drums).opus").write_text("d")
    cli.main(["tidy", str(show)])
    assert sorted(os.listdir(show / "007 - New")) == ["007 - New.opus", "drums.opus"]
    record = json.loads((show / layout.RECORD).read_text())
    assert any(new.startswith("007 - New/") for _, new in record["moves"]) and any(new.startswith(A) for _, new in record["moves"])
    cli.main(["tidy", "--undo", str(show)])
    assert (show / "007 - New (drums).opus").exists() and (show / f"{A} (drums).opus").exists()
    assert next(f for f in ui.library(tmp_path) if f["name"] == "Show")["old"] == 3
