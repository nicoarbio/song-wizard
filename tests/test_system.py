"""Opening links and folders, the log and the report."""

import os
import subprocess

import pytest

from song_wizard import __version__, cli, log, report, system


def test_folder_command(monkeypatch, tmp_path):
    monkeypatch.setattr(system, "is_wsl", lambda: False)
    monkeypatch.setattr(system.sys, "platform", "darwin")
    assert system.folder_command(tmp_path) == ["open", str(tmp_path)]
    monkeypatch.setattr(system.sys, "platform", "linux")
    monkeypatch.setattr(system.shutil, "which", lambda name: f"/usr/bin/{name}")
    assert system.folder_command(tmp_path) == ["xdg-open", str(tmp_path)]
    monkeypatch.setattr(system.shutil, "which", lambda name: None)
    assert system.folder_command(tmp_path) is None


def test_folder_command_wsl(monkeypatch, tmp_path):
    monkeypatch.setattr(system, "is_wsl", lambda: True)
    monkeypatch.setattr(system.shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(system, "windows_path", lambda path: "C:\\Users\\me\\Music\\Show")
    assert system.folder_command(tmp_path) == ["explorer.exe", "C:\\Users\\me\\Music\\Show"]


def test_open_url_wsl_escapes_ampersands(monkeypatch):
    calls = []
    monkeypatch.setattr(system, "is_wsl", lambda: True)
    monkeypatch.setattr(system.shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(system, "launch", calls.append)
    system.open_url("https://example.com/new?title=a&body=b%26c")
    assert calls == [["cmd.exe", "/c", "start", "", "https://example.com/new?title=a^&body=b%26c"]]


def log_text():
    return log.path().read_text(encoding="utf-8")


@pytest.fixture
def logging_on(monkeypatch):
    monkeypatch.delenv(log.OFF)


def test_log_records_command_and_result(logging_on):
    cli.main(["config"])
    text = log_text()
    assert f"song-wizard {__version__}" in text and ": config" in text and "done in" in text


def test_log_records_errors(logging_on, tmp_path):
    with pytest.raises(SystemExit):
        cli.main(["click", "120", "--meter", "nope"])
    assert 'Invalid meter "nope"' in log_text()
    assert "ended with exit code 1" in log_text()


def test_log_records_crashes_with_subprocess_output(logging_on, monkeypatch):
    from song_wizard import config

    def broken():
        subprocess.run(["sh", "-c", "echo bad input >&2; exit 3"], capture_output=True, check=True)

    monkeypatch.setattr(config, "show", broken)
    with pytest.raises(subprocess.CalledProcessError):
        cli.main(["config"])
    text = log_text()
    assert "crashed after" in text and "Traceback" in text
    assert "its output:\nbad input" in text


def test_log_off(monkeypatch):
    cli.main(["config"])
    assert not log.path().exists()


def test_private(monkeypatch, tmp_path):
    monkeypatch.setattr(report.Path, "home", lambda: tmp_path / "home" / "someone")
    text = (f"{tmp_path}/home/someone/Music/a.opus\n/mnt/c/Users/Some One/Music\n"
            "/mnt/d/Users/someone/x\nC:\\Users\\someone\\Music\\Show\nD:\\Music")
    assert report.private(text) == (
        "~/Music/a.opus\n/mnt/c/Users/~ One/Music\n/mnt/d/Users/~/x\nC:\\Users\\~\\Music\\Show\nD:\\Music")


def earlier_log(*lines):
    """A log written by an earlier command (another process)."""
    log.LOG_DIR.mkdir(parents=True, exist_ok=True)
    log.path().write_text("".join(f"2026-10-31 20:00:00 [1] ERROR {line}\n" for line in lines), encoding="utf-8")


def test_report(monkeypatch, tmp_path):
    monkeypatch.setattr(report, "setup_output", lambda: "Everything is ready.")
    monkeypatch.setattr(report.Path, "home", lambda: tmp_path)
    earlier_log(f"song-wizard 0.1.0: key {tmp_path}/Music/song.opus", f"something broke in {tmp_path}/Music")
    path, text, url = report.build()
    assert path.parent == report.REPORTS_DIR and path.read_text(encoding="utf-8") == text
    assert "Everything is ready." in text and "something broke in ~/Music" in text
    assert str(tmp_path) not in text
    assert url.startswith(report.ISSUES + "?") and len(url) <= report.URL_LIMIT
    assert "something+broke+in+~%2FMusic" in url or "something+broke+in+%7E%2FMusic" in url


def test_report_link_fits(monkeypatch):
    monkeypatch.setattr(report, "setup_output", lambda: "ok")
    earlier_log(*(f"line {i} {'x' * 300}" for i in range(200)))
    _, text, url = report.build()
    assert "line 199" in text and len(url) <= report.URL_LIMIT
    assert "line+199" in url  # the last line made it, shortened


def test_report_command_without_terminal(logging_on, monkeypatch, capsys):
    opened = []
    monkeypatch.setattr(report, "setup_output", lambda: "ok")
    monkeypatch.setattr(report.system, "open_url", opened.append)
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    cli.main(["report"])
    out = capsys.readouterr().out
    assert "Report saved to" in out and report.ISSUES in out
    assert opened == []
    assert len(os.listdir(report.REPORTS_DIR)) == 1
