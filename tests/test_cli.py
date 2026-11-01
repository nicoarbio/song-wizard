"""Every subcommand must reach its module: none may fall through to the help text."""

import importlib

import pytest

from song_wizard import cli

# command -> (arguments, module, function that must be called)
DISPATCH = {
    "download": (["https://example.com/watch?v=x"], "download", "run"),
    "key": (["song.opus"], "key", "run"),
    "bpm": (["song.opus"], "bpm", "run"),
    "click": (["120"], "click", "run"),
    "transpose": (["--", "-2", "song.opus"], "transpose", "run"),
    "align": (["song.opus"], "align", "run"),
    "speed": (["80", "song.opus"], "speed", "run"),
    "separate": (["--stem", "drums", "song.opus"], "separate", "run"),
    "convert": (["song.wav"], "convert", "run"),
    "rename": (["song.opus", "New"], "rename", "run"),
    "trim": (["song.opus", "--start", "5"], "trim", "run"),
    "delete": (["song.opus"], "delete", "run"),
    "archives": ([], "archives", "show"),
    "ui": (["--no-browser"], "ui", "run"),
    "config": ([], "config", "show"),
    "report": ([], "report", "run"),
    "list": ([], "listing", "run"),
    "setlist": ([], "setlist", "run"),
    "lyrics": (["song.opus"], "lyrics", "run"),
    "reaper": (["song.opus"], "reaper", "run"),
    "setup": ([], "setup", "run"),
}


def subcommands():
    parser = cli.build_parser()
    sub = next(a for a in parser._actions if a.dest == "command")
    return set(sub.choices)


def test_every_subcommand_is_covered():
    assert subcommands() == set(DISPATCH) | {"upgrade", "open"}  # both have their own tests


@pytest.mark.parametrize("command", sorted(DISPATCH))
def test_dispatch(command, monkeypatch):
    args, module_name, function = DISPATCH[command]
    module = importlib.import_module(f"song_wizard.{module_name}")
    calls = []
    monkeypatch.setattr(module, function, lambda *a, **k: calls.append((a, k)))
    monkeypatch.setattr(cli.argparse.ArgumentParser, "print_help",
                        lambda *a, **k: pytest.fail("fell through to print_help"))
    cli.main([command, *args])
    assert len(calls) == 1


def test_transpose_negative_semitones(monkeypatch):
    from song_wizard import transpose
    calls = []
    monkeypatch.setattr(transpose, "run", lambda *a: calls.append(a))
    cli.main(["transpose", "--", "-2", "song.opus"])
    assert calls == [(-2.0, ["song.opus"])]


def test_speed_with_semitones(monkeypatch):
    from song_wizard import speed
    calls = []
    monkeypatch.setattr(speed, "run", lambda *a, **k: calls.append((a, k)))
    cli.main(["speed", "87.5", "--semitones", "-2", "a.opus", "b.opus"])
    assert calls == [((87.5, ["a.opus", "b.opus"]), {"semitones": -2.0})]


def test_archives_delete(monkeypatch):
    from song_wizard import archives
    calls = []
    monkeypatch.setattr(archives, "delete", lambda which, yes: calls.append((which, yes)))
    cli.main(["archives", "--delete", "1", "3", "--yes"])
    assert calls == [(["1", "3"], True)]


def test_upgrade(monkeypatch):
    from song_wizard import updates
    calls = []
    monkeypatch.setattr(updates, "upgrade", lambda: calls.append("upgrade") or 0)
    monkeypatch.setattr(updates, "to", lambda v: calls.append(("to", v)) or 0)
    for args in (["upgrade"], ["upgrade", "--to", "0.12.0"]):
        with pytest.raises(SystemExit) as e:
            cli.main(args)
        assert e.value.code == 0
    assert calls == ["upgrade", ("to", "0.12.0")]


def test_no_command_shows_help(capsys):
    with pytest.raises(SystemExit) as e:
        cli.main([])
    assert e.value.code == 1
    assert "usage: song-wizard" in capsys.readouterr().out


def test_version_in_one_place():
    import tomllib
    from pathlib import Path

    from song_wizard import __version__
    project = tomllib.loads((Path(__file__).parent.parent / "pyproject.toml").read_text())
    assert project["project"]["version"] == __version__


def test_separate_drumkit_option(monkeypatch):
    from song_wizard import separate
    calls = []
    monkeypatch.setattr(separate, "run", lambda stems, paths, **k: calls.append(stems))
    cli.main(["separate", "--stem", "drumkit", "song.opus"])
    assert calls == [["drumkit"]]
