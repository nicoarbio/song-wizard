import pytest

from song_wizard import archives, config, paths


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    """Never touch the real settings, archives or music folder."""
    data = tmp_path / "data"
    monkeypatch.setattr(config, "CONFIG_PATH", tmp_path / "config" / "config.toml")
    monkeypatch.setattr(paths, "ARCHIVE_DIR", data / "archives")
    monkeypatch.setattr(archives, "ARCHIVE_DIR", data / "archives")
    monkeypatch.setattr(paths, "MODELS_DIR", data / "models")
    monkeypatch.delenv("SONG_WIZARD_DIR", raising=False)
    return tmp_path
