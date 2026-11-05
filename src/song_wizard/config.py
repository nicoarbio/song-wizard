"""Local settings in a TOML file. Command-line options always win over it."""

import os
import sys
import tomllib
from pathlib import Path

from platformdirs import user_config_dir

# SONG_WIZARD_CONFIG points somewhere else (the tests: the commands they run as subprocesses must
# not read the real settings).
CONFIG_PATH = Path(os.environ.get("SONG_WIZARD_CONFIG") or Path(user_config_dir("song-wizard", appauthor=False)) / "config.toml")

DEFAULTS = {
    "download": {"music_dir": None},
    "audio": {"stems": "opus"},
}

TEMPLATE = """\
# song-wizard settings. Uncomment a line to change a default;
# options given on the command line always win over this file.

[download]
# Where downloads go (default: your Music folder, the Windows one on WSL).
# The SONG_WIZARD_DIR environment variable wins over this.
# music_dir = "~/Ensayos"

[audio]
# Format of the stems and versions song-wizard makes (drums, bass, speed, transposed...):
# "opus" (default: ~1.1 MB a minute per stem, and Practice jumps in it as exactly as in WAV),
# "wav" (32-bit float, ~20 MB a minute per stem: to edit them in another program) or "mp3"
# (~1.4 MB a minute, but in Practice the tracks drift apart after a jump: not for practicing).
# stems = "opus"
"""


def load():
    settings = {section: dict(values) for section, values in DEFAULTS.items()}
    if not CONFIG_PATH.exists():
        return settings
    try:
        with CONFIG_PATH.open("rb") as f:
            user = tomllib.load(f)
    except tomllib.TOMLDecodeError as e:
        sys.exit(f"Error in {CONFIG_PATH}: {e}")
    for section, values in user.items():
        if section in settings and isinstance(values, dict):
            settings[section].update(values)
    return settings


def get(section, key):
    return load()[section][key]


def ensure():
    """Write the settings file (everything commented out) if it isn't there. True if it was written."""
    if CONFIG_PATH.exists():
        return False
    try:
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        CONFIG_PATH.write_text(TEMPLATE)
    except OSError:
        return False  # a read-only home: the defaults apply all the same
    return True


def read_text():
    """The settings file as written (made first, all commented out, if it isn't there)."""
    ensure()
    try:
        return CONFIG_PATH.read_text(encoding="utf-8")
    except OSError:
        return TEMPLATE


def write_text(text):
    """Save the settings file as given, if it's valid TOML (else tomllib.TOMLDecodeError, a
    ValueError). Written whole or not at all."""
    tomllib.loads(text)
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    temp = CONFIG_PATH.with_name(f".{CONFIG_PATH.name}.tmp")
    temp.write_text(text, encoding="utf-8")
    os.replace(temp, CONFIG_PATH)


def show():
    if ensure():
        print(f"Created {CONFIG_PATH} (everything commented out: defaults apply)\n")
    else:
        print(f"Settings file: {CONFIG_PATH}\n")
    for section, values in load().items():
        print(f"[{section}]")
        for key, value in values.items():
            print(f"  {key} = {value if value is not None else '(default)'}")
