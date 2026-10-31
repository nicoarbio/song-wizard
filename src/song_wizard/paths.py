import os
import re
import shutil
import subprocess
from pathlib import Path

from platformdirs import user_data_dir

DATA_DIR = Path(user_data_dir("song-wizard", appauthor=False))
ARCHIVE_DIR = DATA_DIR / "archives"
MODELS_DIR = DATA_DIR / "models"


def is_wsl():
    try:
        return "microsoft" in Path("/proc/version").read_text().lower()
    except OSError:
        return False


def music_dir():
    """Where downloads go: $SONG_WIZARD_DIR, else music_dir in the config file, else the
    Windows Music folder on WSL, else ~/Music."""
    from . import config

    if env := os.environ.get("SONG_WIZARD_DIR"):
        return Path(env).expanduser()
    if configured := config.get("download", "music_dir"):
        return Path(configured).expanduser()
    if is_wsl() and shutil.which("cmd.exe") and shutil.which("wslpath"):
        # Run from a Windows drive: from a Linux folder cmd.exe prints a localized (non-UTF-8)
        # warning about UNC paths.
        out = subprocess.run(["cmd.exe", "/c", "echo %USERPROFILE%"], capture_output=True,
                             cwd="/mnt/c" if os.path.isdir("/mnt/c") else None).stdout
        lines = [l.strip() for l in out.decode(errors="replace").splitlines()]
        win_home = next((l for l in lines if re.match(r"^[A-Za-z]:\\", l)), None)
        if win_home:
            linux_home = subprocess.run(["wslpath", win_home], capture_output=True, text=True).stdout.strip()
            return Path(linux_home) / "Music"
    return Path.home() / "Music"
