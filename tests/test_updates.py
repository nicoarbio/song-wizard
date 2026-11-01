"""Whether there's a newer song-wizard, and upgrading from the interface."""

import json

import pytest

from song_wizard import __version__, cli, ui, updates
from test_ui import TOKEN, request, server  # noqa: F401  (the fixture)


def test_compare():
    assert updates.parse("0.13.2") == (0, 13, 2) and updates.parse("v1") is None
    assert updates.newer("0.10.0", "0.9.9") and not updates.newer("0.9.9", "0.10.0") and not updates.newer("x", "0.1")


class Answer:
    def __init__(self, data): self.data = data
    def read(self, n): return self.data
    def __enter__(self): return self
    def __exit__(self, *a): pass


# What GitHub answers to git's "which refs are there": annotated tags come twice (with ^{}).
REFS = (b"001e# service=git-upload-pack\n0000"
        b"003f1111 refs/heads/main\n"
        b"003f2222 refs/tags/v0.9.0\n003f3333 refs/tags/v0.9.0^{}\n"
        b"003f4444 refs/tags/v0.10.0\n003f5555 refs/tags/v0.10.0^{}\n"
        b"003f6666 refs/tags/v0.2.0\n003f7777 refs/tags/experiment\n0000")


def test_versions_from_the_tags(monkeypatch):
    monkeypatch.setattr(updates.urllib.request, "urlopen", lambda req, timeout: Answer(REFS))
    assert updates.versions() == ["0.2.0", "0.9.0", "0.10.0"] and updates.latest() == "0.10.0"

    def offline(req, timeout):
        raise OSError("no network")
    monkeypatch.setattr(updates.urllib.request, "urlopen", offline)
    assert updates.latest() is None


def test_list_upgrade_and_to(monkeypatch, capsys):
    monkeypatch.setattr(updates.urllib.request, "urlopen", lambda req, timeout: Answer(REFS))
    monkeypatch.setattr(updates, "__version__", "0.9.0")
    monkeypatch.setattr(updates, "source", lambda: "git")
    ran = []
    monkeypatch.setattr(updates, "uv", lambda *args: ran.append(args) or 0)
    updates.show()
    out = capsys.readouterr().out
    assert out.index("0.10.0") < out.index("0.9.0  ← installed") < out.index("0.2.0")
    # A newer tag: that tag is installed (not the latest commit).
    assert updates.upgrade() == 0
    assert ran[-1] == ("tool", "install", "--force", "--upgrade", f"song-wizard @ git+{updates.REPO}@v0.10.0")
    # The newest already: only what it uses gets updated.
    monkeypatch.setattr(updates, "__version__", "0.10.0")
    updates.upgrade()
    assert ran[-1] == ("tool", "upgrade", "song-wizard")
    # An older one, by number; one that doesn't exist, refused.
    assert updates.to("v0.2.0") == 0 and ran[-1][-1].endswith("@v0.2.0")
    assert "can't move to a newer one by themselves" in capsys.readouterr().out
    with pytest.raises(SystemExit):
        updates.to("0.3.0")
    # Installed from a folder with the code: upgrading takes the folder again.
    monkeypatch.setattr(updates, "source", lambda: "directory")
    updates.upgrade()
    assert ran[-1] == ("tool", "upgrade", "--reinstall", "song-wizard")


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


def test_upgrade_loads_what_it_needs_before_installing(tmp_path):
    """The install replaces the files under the running process: anything imported afterwards
    would come from the new version and could clash with the old modules already loaded
    (0.6.0 → 0.15.0 crashed that way right after a good install). So by the time it installs,
    everything used afterwards is loaded."""
    import subprocess
    import sys
    script = (
        "import sys\n"
        "from song_wizard import cli, updates\n"
        "def fake():\n"
        "    print('ui loaded:', 'song_wizard.ui' in sys.modules)\n"
        "    return 1\n"
        "updates.upgrade = fake\n"
        "cli.main(['upgrade'])\n")
    env = {**__import__("os").environ, "SONG_WIZARD_UI_STATE": str(tmp_path / "ui.json")}
    out = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, env=env)
    assert "ui loaded: True" in out.stdout, out.stdout + out.stderr
