"""The interface running in the background: started once, found again, closed with --stop."""

import json
import os
import socket
import time

import pytest

from song_wizard import cli, ui


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def music(tmp_path, monkeypatch):
    root = tmp_path / "music"
    root.mkdir()
    monkeypatch.setenv("SONG_WIZARD_DIR", str(root))
    # The server is another process: it must not see the real data folder either.
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))
    yield root
    ui.stop(yes=True)


def test_nothing_running(capsys):
    assert ui.running() is None
    ui.stop()
    assert "isn't running" in capsys.readouterr().out


def test_stale_state_is_ignored(tmp_path):
    ui.write_state({"pid": 1, "port": free_port(), "token": "x", "url": "http://x", "root": str(tmp_path)})
    assert ui.running() is None
    assert oct(os.stat(ui.state_file()).st_mode & 0o777) == "0o600"  # it holds the token


def test_background_start_reuse_and_stop(music, monkeypatch, capsys):
    opened = []
    monkeypatch.setattr(ui.system, "open_url", opened.append)
    port = free_port()
    cli.main(["ui", "--port", str(port)])  # returns: the server lives on in its own process
    info = ui.running()
    assert info and info["port"] == port and info["pid"] != os.getpid() and info["root"] == str(music)
    assert opened == [info["url"]]
    assert "--stop" in capsys.readouterr().out
    # Again: the same server, no second one.
    cli.main(["ui", "--port", str(port)])
    assert ui.running()["pid"] == info["pid"] and opened[1] == info["url"]
    assert "already running" in capsys.readouterr().out
    # Restart: a new server (new process, new link), opened in the browser.
    cli.main(["ui", "--restart", "--port", str(port)])
    again = ui.running()
    assert again and again["pid"] != info["pid"] and again["url"] != info["url"] and opened[-1] == again["url"]
    assert "closed" in capsys.readouterr().out
    cli.main(["ui", "--stop"])
    assert ui.running() is None and not ui.state_file().exists()
    assert "closed" in capsys.readouterr().out


def test_another_music_folder(music, monkeypatch, tmp_path):
    monkeypatch.setattr(ui.system, "open_url", lambda url: None)
    ui.run(port=free_port())
    other = tmp_path / "other"
    other.mkdir()
    monkeypatch.setenv("SONG_WIZARD_DIR", str(other))
    with pytest.raises(SystemExit, match="another music folder"):
        ui.run(port=free_port())


def test_stop_asks_while_working(music, monkeypatch, capsys):
    monkeypatch.setattr(ui.system, "open_url", lambda url: None)
    ui.run(port=free_port())
    real = ui.ask
    with monkeypatch.context() as m:
        m.setattr(ui, "ask", lambda port, token, method, path, timeout=3:
                  (200, [{"title": "Separar: song.opus", "status": "running"}]) if path == "/api/jobs" and port
                  else real(port, token, method, path, timeout))
        m.setattr(ui.sys, "stdin", open(os.devnull))
        with pytest.raises(SystemExit, match="--yes"):
            ui.stop()
        with pytest.raises(SystemExit, match="--yes"):  # restart doesn't start a second one either
            cli.main(["ui", "--restart"])
    assert "Separar: song.opus" in capsys.readouterr().out
    assert ui.running()  # still there


def test_started_server_is_recognized_by_its_word_not_its_process_number(music, monkeypatch):
    """On a Mac, Python can hand over to another process: the number the launcher saw isn't the
    server's. Starting must still find it (this failed on the Mac CI)."""
    real = ui.subprocess.Popen

    class Launcher:  # what the starter sees: a process whose number isn't the server's
        def __init__(self, *args, **kwargs):
            self.inner = real(*args, **kwargs)
            self.pid = -1

        def poll(self):
            return self.inner.poll()

        def kill(self):
            self.inner.kill()
    monkeypatch.setattr(ui.subprocess, "Popen", Launcher)
    monkeypatch.setattr(ui.system, "open_url", lambda url: None)
    ui.run(port=free_port())
    assert ui.running()


def test_shutdown_from_the_page(music, monkeypatch):
    monkeypatch.setattr(ui.system, "open_url", lambda url: None)
    ui.run(port=free_port())
    info = ui.running()
    status, _ = ui.ask(info["port"], info["token"], "POST", "/api/shutdown")
    assert status == 200
    for _ in range(50):
        if not ui.running():
            break
        time.sleep(0.1)
    assert ui.running() is None
    # Without the token, nobody else can close it.
    ui.run(port=free_port())
    info = ui.running()
    assert ui.ask(info["port"], "wrong", "POST", "/api/shutdown")[0] == 403
    assert ui.running()
