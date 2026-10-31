"""Local settings in a TOML file. Command-line options always win over it."""

import sys
import tomllib
from pathlib import Path

from platformdirs import user_config_dir

CONFIG_PATH = Path(user_config_dir("song-wizard", appauthor=False)) / "config.toml"

DEFAULTS = {
    "download": {"music_dir": None},
    "click": {"meter": "4/4", "count_in": 1},
}

TEMPLATE = """\
# song-wizard settings. Uncomment a line to change a default;
# options given on the command line always win over this file.

[download]
# Where downloads go (default: your Music folder, the Windows one on WSL).
# The SONG_WIZARD_DIR environment variable wins over this.
# music_dir = "~/Ensayos"

[click]
# Time signature: the top number is how many clicks per bar, the first one accented.
# meter = "4/4"
# Bars of count-in before the song starts.
# count_in = 1
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


def show():
    if not CONFIG_PATH.exists():
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        CONFIG_PATH.write_text(TEMPLATE)
        print(f"Created {CONFIG_PATH} (everything commented out: defaults apply)\n")
    else:
        print(f"Settings file: {CONFIG_PATH}\n")
    for section, values in load().items():
        print(f"[{section}]")
        for key, value in values.items():
            print(f"  {key} = {value if value is not None else '(default)'}")
