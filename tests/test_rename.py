"""song-wizard rename: the song's folder and the files named after it, or nothing."""

import os

import pytest

from song_wizard import rename, results

# In the song's folder: named after it (they follow the name) and not (they stay as they are).
OWN = ["001 - Song (HQ).opus", "001 - Song (HQ).wav", "001 - Song (HQ).mp3", "001 - Song (HQ).rpp",
       "001 - Song (HQ).opus.reapeaks", "001 - Song (HQ).drums.mid"]
SHORT = ["drums.wav", "no drums.wav", "+2.wav", "drums 80%.wav", "80%, -2.wav", "lyrics.json"]
OTHERS = ["001 - Song (HQ) (Live)", "002 - Other"]


@pytest.fixture
def show(tmp_path):
    here = tmp_path / "001 - Song (HQ)"
    here.mkdir()
    for name in OWN + SHORT:
        (here / name).write_text(name)
    for other in OTHERS:
        (tmp_path / other).mkdir()
        (tmp_path / other / f"{other}.opus").write_text(other)
    results.save(here, "key", "G")
    return tmp_path


def listing(folder):
    return sorted(str(p.relative_to(folder)) for p in folder.rglob("*") if p.is_file())


def test_renames_the_folder_and_its_own_files(show):
    before = listing(show)
    rename.run(str(show / "001 - Song (HQ)" / "001 - Song (HQ).opus"), "Song")
    here = show / "001 - Song"
    assert sorted(os.listdir(here)) == sorted([n.replace("001 - Song (HQ)", "001 - Song", 1) for n in OWN]
                                              + SHORT + ["key.txt"])
    assert (here / "001 - Song.wav").read_text() == "001 - Song (HQ).wav"
    assert (here / "drums 80%.wav").read_text() == "drums 80%.wav"
    assert results.read(here, "key") == "G"
    assert len(listing(show)) == len(before)


def test_from_any_file_of_the_song(show):
    rename.run(str(show / "001 - Song (HQ)" / "no drums.wav"), "Song")
    assert (show / "001 - Song" / "001 - Song.opus").exists() and (show / "001 - Song" / "no drums.wav").exists()


def test_points_its_reaper_project_to_the_new_name(show):
    project = show / "001 - Song (HQ)" / "001 - Song (HQ).rpp"
    project.write_text('<REAPER_PROJECT\n  <SOURCE WAVE\n    FILE "001 - Song (HQ).opus"\n  >\n  FILE "drums.wav"\n>\n')
    rename.run(str(project), "Song")
    text = (show / "001 - Song" / "001 - Song.rpp").read_text()
    assert 'FILE "001 - Song.opus"' in text and 'FILE "drums.wav"' in text


@pytest.mark.parametrize("given, base", [
    ("Song", "001 - Song"), ("  Song  ", "001 - Song"), ("Song.opus", "001 - Song"),
    ("005 - Song", "005 - Song"), ("Song: the remix", None), ("Song?", None), ("a/b", None),
    ("", None), ("Song.", None), ("drums", None), ("80%", None), ("001 - Song (HQ)", None),
    ("002 - Other", None),
])
def test_names(show, given, base):
    song = str(show / "001 - Song (HQ)" / "001 - Song (HQ).opus")
    before = listing(show)
    if base is None:
        with pytest.raises(SystemExit):
            rename.run(song, given)
        assert listing(show) == before
    else:
        rename.run(song, given)
        assert (show / base / f"{base}.opus").exists() and (show / base / "drums.wav").exists()


def test_no_number_to_keep(tmp_path):
    (tmp_path / "Song").mkdir()
    (tmp_path / "Song" / "Song.opus").write_text("x")
    rename.run(str(tmp_path / "Song" / "Song.opus"), "Better")
    assert listing(tmp_path) == ["Better/Better.opus"]


def test_failure_halfway_rolls_back(show, monkeypatch):
    real = os.rename
    calls = []

    def flaky(src, dst):
        calls.append(src)
        if len(calls) == 4:
            raise PermissionError("in use")
        real(src, dst)

    before = listing(show)
    monkeypatch.setattr(rename.os, "rename", flaky)
    with pytest.raises(SystemExit):
        rename.run(str(show / "001 - Song (HQ)" / "001 - Song (HQ).opus"), "Song")
    assert listing(show) == before


def test_case_only_change(tmp_path):
    (tmp_path / "song").mkdir()
    (tmp_path / "song" / "song.opus").write_text("x")
    (tmp_path / "song" / "drums.wav").write_text("y")
    rename.run(str(tmp_path / "song" / "song.opus"), "Song")
    assert listing(tmp_path) == ["Song/Song.opus", "Song/drums.wav"]


def test_same_name(show):
    with pytest.raises(SystemExit):
        rename.run(str(show / "001 - Song (HQ)" / "001 - Song (HQ).opus"), "001 - Song (HQ)")


def test_missing_file(tmp_path):
    with pytest.raises(SystemExit):
        rename.run(str(tmp_path / "nope.opus"), "Song")


def test_reaper_peaks_folder_follows(show):
    peaks = show / "001 - Song (HQ)" / "peaks"
    peaks.mkdir()
    (peaks / "001 - Song (HQ).opus.reapeaks").write_text("p")
    (peaks / "drums.wav.reapeaks").write_text("d")
    rename.run(str(show / "001 - Song (HQ)" / "001 - Song (HQ).opus"), "Song")
    assert sorted(os.listdir(show / "001 - Song" / "peaks")) == ["001 - Song.opus.reapeaks", "drums.wav.reapeaks"]
