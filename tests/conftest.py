import pytest

from song_wizard import archives, config, log, paths, report


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    """Never touch the real settings, archives or music folder."""
    data = tmp_path / "data"
    monkeypatch.setattr(config, "CONFIG_PATH", tmp_path / "config" / "config.toml")
    monkeypatch.setattr(paths, "ARCHIVE_DIR", data / "archives")
    monkeypatch.setattr(archives, "ARCHIVE_DIR", data / "archives")
    monkeypatch.setattr(paths, "MODELS_DIR", data / "models")
    monkeypatch.setattr(log, "LOG_DIR", data / "logs")
    monkeypatch.setattr(report, "REPORTS_DIR", data / "reports")
    monkeypatch.delenv("SONG_WIZARD_DIR", raising=False)
    # Commands the tests run as subprocesses (interface jobs) must not log to the real log.
    monkeypatch.setenv(log.OFF, "1")
    return tmp_path
