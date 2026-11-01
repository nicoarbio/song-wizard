"""Whether there's a newer song-wizard, and upgrading from the interface."""

import json

import pytest

from song_wizard import __version__, cli, ui, updates
from test_ui import TOKEN, request, server  # noqa: F401  (the fixture)


def test_compare():
    assert updates.parse("0.13.2") == (0, 13, 2) and updates.parse("v1") is None
    assert updates.newer("0.10.0", "0.9.9") and not updates.newer("0.9.9", "0.10.0") and not updates.newer("x", "0.1")


def test_latest_reads_the_published_version(monkeypatch):
    class Answer:
        def __init__(self, text): self.text = text
        def read(self, n): return self.text.encode()
        def __enter__(self): return self
        def __exit__(self, *a): pass
    monkeypatch.setattr(updates.urllib.request, "urlopen", lambda req, timeout: Answer('[project]\nname = "x"\nversion = "9.1.0"\n'))
    assert updates.latest() == "9.1.0"

    def offline(req, timeout):
        raise OSError("no network")
    monkeypatch.setattr(updates.urllib.request, "urlopen", offline)
    assert updates.latest() is None


@pytest.mark.parametrize("found, says", [("99.0.0", "99.0.0 is out"), (__version__, "up to date"), (None, "Couldn't check")])
def test_upgrade_check(monkeypatch, capsys, found, says):
    monkeypatch.setattr(updates, "latest", lambda: found)
    cli.main(["upgrade", "--check"])
    assert says in capsys.readouterr().out


def test_interface(server, monkeypatch):  # noqa: F811
    port, root = server
    monkeypatch.setattr(ui, "_latest", {"at": 0.0, "version": None})
    asked = []
    monkeypatch.setattr(updates, "latest", lambda: asked.append(1) or "99.0.0")
    got = json.loads(request(port, "GET", "/api/version")[1])
    assert got == {"current": __version__, "latest": "99.0.0", "newer": True, "server": ui.SERVER_ID}
    request(port, "GET", "/api/version")
    assert len(asked) == 1  # remembered for a while...
    request(port, "GET", "/api/version?check=1")
    assert len(asked) == 2  # ...unless asked to look again
    # The upgrade job runs the CLI's upgrade.
    handler = ui.make_handler(TOKEN, root, ui.Runner(), port)
    assert handler.command_for(None, {"action": "upgrade"}) == ("Actualizar song-wizard", ["upgrade"])


def test_restart_endpoint(server, monkeypatch):  # noqa: F811
    port, _ = server
    restarted = []
    monkeypatch.setattr(ui, "restart", restarted.append)
    assert request(port, "POST", "/api/restart", {})[0].status == 200 and restarted == [port]
