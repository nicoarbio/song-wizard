import pytest

from song_wizard import archives, config, log, paths, reaper, report, ui


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    """Never touch the real settings, archives or music folder."""
    data = tmp_path / "data"
    monkeypatch.setattr(config, "CONFIG_PATH", tmp_path / "config" / "config.toml")
    monkeypatch.setenv("SONG_WIZARD_CONFIG", str(tmp_path / "config" / "config.toml"))  # and the subprocesses
    monkeypatch.setattr(paths, "ARCHIVE_DIR", data / "archives")
    monkeypatch.setattr(archives, "ARCHIVE_DIR", data / "archives")
    monkeypatch.setattr(paths, "MODELS_DIR", data / "models")
    monkeypatch.setattr(log, "LOG_DIR", data / "logs")
    monkeypatch.setattr(report, "REPORTS_DIR", data / "reports")
    monkeypatch.delenv("SONG_WIZARD_DIR", raising=False)
    # Commands the tests run as subprocesses (interface jobs) must not log to the real log.
    monkeypatch.setenv(log.OFF, "1")
    # Nor find (or stop) the real interface if it's running.
    monkeypatch.setenv("SONG_WIZARD_UI_STATE", str(data / "ui.json"))
    # Nor REAPER: its settings, or opening it. Tests that need it installed or running say so.
    monkeypatch.setattr(reaper, "ini_path", lambda: tmp_path / "REAPER" / "reaper.ini")
    monkeypatch.setattr(reaper, "installed", lambda: False)
    monkeypatch.setattr(reaper, "running", lambda: False)
    monkeypatch.setattr(reaper, "STATE", data / "reaper.json")
    monkeypatch.setattr(ui, "_reaper", {"at": 0.0, "installed": False})
    return tmp_path
