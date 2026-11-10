"""Commands that give the terminal what the interface does: list, open, archives --update,
ui --practice."""

import pytest

from song_wizard import archives, cli, listing, results, system, ui


@pytest.fixture
def music(tmp_path, monkeypatch):
    root = tmp_path / "music"
    show = root / "Show"
    show.mkdir(parents=True)
    for name in ["001 - Song/001 - Song.opus", "001 - Song/drums.wav", "001 - Song/80%.wav", "002 - Other/002 - Other.opus"]:
        (show / name).parent.mkdir(exist_ok=True)
        (show / name).write_bytes(b"x")
    results.save(show / "001 - Song", "key", "G    G major   relative Em    4/4")
    results.save(show / "001 - Song", "tempo", "120.00 BPM 4/4, first beat 0.500 s")
    monkeypatch.setenv("SONG_WIZARD_DIR", str(root))
    return root


def test_list(music, capsys):
    listing.run()
    out = capsys.readouterr().out
    assert f"{music / 'Show'}  (2 songs)" in out
    assert "  001 - Song.opus  ·  G  ·  120.00 BPM 4/4 from 0.500 s  ·  +2 files" in out
    assert "  002 - Other.opus\n" in out


def test_list_text_and_files(music, capsys):
    listing.run("song", files=True)
    out = capsys.readouterr().out
    assert "001 - Song.opus" in out and "002 - Other" not in out
    assert "      drums.wav" in out and "+2 files" not in out
    listing.run("nothing like it")
    assert "Nothing found." in capsys.readouterr().out


def test_open(music, monkeypatch, capsys):
    opened = []
    monkeypatch.setattr(system, "open_folder", lambda p: opened.append(p) or True)
    cli.main(["open"])
    cli.main(["open", str(music / "Show" / "001 - Song" / "001 - Song.opus")])
    assert opened == [music, music / "Show" / "001 - Song"]
    with pytest.raises(SystemExit):
        cli.main(["open", str(music / "nope")])


def test_archives_update(monkeypatch, capsys):
    archives.ARCHIVE_DIR.mkdir(parents=True)
    for archive_id, wav in [("PLa", True), ("PLb", False)]:
        (archives.ARCHIVE_DIR / f"{archive_id}.txt").write_text("site x\n")
        archives.remember(archive_id, f"https://example.com/playlist?list={archive_id}", archive_id, wav=wav)
    (archives.ARCHIVE_DIR / "singles.txt").write_text("site y\n")
    fetched = []
    monkeypatch.setattr("song_wizard.download.fetch", lambda url, wav=False: fetched.append((url, wav)) or 0)
    archives.update(["2"])
    archives.update(["all"])
    assert fetched == [("https://example.com/playlist?list=PLb", False),
                       ("https://example.com/playlist?list=PLa", True), ("https://example.com/playlist?list=PLb", False)]
    with pytest.raises(SystemExit):
        archives.update(["3"])  # singles: no playlist to look in


def test_practice_link(music):
    show = music / "Show"
    assert ui.page_path(music, show / "001 - Song" / "drums.wav") == "Show/001 - Song/001 - Song.opus"
    assert ui.page_path(music, show / "002 - Other" / "002 - Other.opus") == "Show/002 - Other/002 - Other.opus"
    assert ui.page_path(music, music / "elsewhere.opus") is None
