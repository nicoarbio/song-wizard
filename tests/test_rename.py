"""song-wizard rename: the whole group or nothing."""

import os

import pytest

from song_wizard import rename, results

SONG = [
    "001 - Song (HQ).opus", "001 - Song (HQ).wav", "001 - Song (HQ).mp3", "001 - Song (HQ) (drums).wav",
    "001 - Song (HQ) (no drums).wav", "001 - Song (HQ) (+2).wav", "001 - Song (HQ) (drums) (80%).wav",
    "001 - Song (HQ) (80%, -2).wav",
]
OTHERS = ["001 - Song (HQ) (Live).opus", "002 - Other.opus", "Click 120 BPM 4-4.wav", "notes.txt"]


@pytest.fixture
def show(tmp_path):
    for name in SONG + OTHERS:
        (tmp_path / name).write_text(name)
    results.save("key", [(str(tmp_path / "001 - Song (HQ).opus"), "G"), (str(tmp_path / "002 - Other.opus"), "Am")])
    results.save("bpm", [(str(tmp_path / "001 - Song (HQ) (drums).wav"), "120.0 BPM  steady")])
    return tmp_path


def names(folder):
    return sorted(n for n in os.listdir(folder) if not n.endswith(".txt") or n == "notes.txt")


def test_renames_the_whole_group(show):
    rename.run(str(show / "001 - Song (HQ).opus"), "Song")
    expected = sorted([n.replace("001 - Song (HQ)", "001 - Song", 1) for n in SONG] + OTHERS)
    assert names(show) == expected
    # Contents moved with their names.
    assert (show / "001 - Song (drums) (80%).wav").read_text() == "001 - Song (HQ) (drums) (80%).wav"
    assert results.read(str(show), "key") == {"001 - Song.opus": "G", "002 - Other.opus": "Am"}
    assert results.read(str(show), "bpm") == {"001 - Song (drums).wav": "120.0 BPM  steady"}


def test_from_any_file_of_the_group(show):
    rename.run(str(show / "001 - Song (HQ) (no drums).wav"), "Song")
    assert (show / "001 - Song.opus").exists() and (show / "001 - Song (no drums).wav").exists()


@pytest.mark.parametrize("given, base", [
    ("Song", "001 - Song"), ("  Song  ", "001 - Song"), ("Song.opus", "001 - Song"),
    ("005 - Song", "005 - Song"), ("Song: the remix", None), ("Song?", None), ("a/b", None),
    ("", None), ("Song.", None), ("Song (drums)", None), ("Song (+2)", None), ("001 - Song (HQ)", None),
])
def test_names(show, given, base):
    if base is None:
        with pytest.raises(SystemExit):
            rename.run(str(show / "001 - Song (HQ).opus"), given)
        assert names(show) == sorted(SONG + OTHERS)
    else:
        rename.run(str(show / "001 - Song (HQ).opus"), given)
        assert (show / f"{base}.opus").exists() and (show / f"{base} (drums).wav").exists()


def test_no_number_to_keep(tmp_path):
    (tmp_path / "Song.opus").write_text("x")
    rename.run(str(tmp_path / "Song.opus"), "Better")
    assert os.listdir(tmp_path) == ["Better.opus"]


def test_clash_renames_nothing(show, capsys):
    (show / "001 - Song (drums).wav").write_text("someone else's")
    with pytest.raises(SystemExit) as e:
        rename.run(str(show / "001 - Song (HQ).opus"), "Song")
    assert "001 - Song (drums).wav" in str(e.value) or "001 - Song (drums).wav" in capsys.readouterr().err
    assert (show / "001 - Song (HQ).opus").exists()
    assert (show / "001 - Song (drums).wav").read_text() == "someone else's"
    assert results.read(str(show), "key")["001 - Song (HQ).opus"] == "G"


def test_failure_halfway_rolls_back(show, monkeypatch):
    real = os.rename
    calls = []

    def flaky(src, dst):
        calls.append(src)
        if len(calls) == 4:
            raise PermissionError("in use")
        real(src, dst)

    monkeypatch.setattr(rename.os, "rename", flaky)
    with pytest.raises(SystemExit):
        rename.run(str(show / "001 - Song (HQ).opus"), "Song")
    assert names(show) == sorted(SONG + OTHERS)
    assert results.read(str(show), "key")["001 - Song (HQ).opus"] == "G"


def test_case_only_change(tmp_path):
    (tmp_path / "song.opus").write_text("x")
    (tmp_path / "song (drums).wav").write_text("y")
    rename.run(str(tmp_path / "song.opus"), "Song")
    assert sorted(os.listdir(tmp_path)) == ["Song (drums).wav", "Song.opus"]


def test_same_name(show):
    with pytest.raises(SystemExit):
        rename.run(str(show / "001 - Song (HQ).opus"), "001 - Song (HQ)")


def test_missing_file(tmp_path):
    with pytest.raises(SystemExit):
        rename.run(str(tmp_path / "nope.opus"), "Song")
