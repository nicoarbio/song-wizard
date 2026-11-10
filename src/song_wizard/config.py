"""Local settings in a TOML file. Command-line options always win over it."""

import os
import re
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
    "reaper": {"count_in": 4},
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

[reaper]
# Bars of click, at least, before the song's first beat in a new REAPER project (0: none).
# count_in = 4
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


HEADER = re.compile(r"^\s*\[([^\]]+)\]\s*(?:#.*)?$")
SETTING = re.compile(r"^\s*#?\s*([A-Za-z_][\w-]*)\s*=")


def sections(text):
    """[(section or None, [lines])] of a settings file, in order."""
    found = [(None, [])]
    for line in text.splitlines():
        if m := HEADER.match(line):
            found.append((m[1].strip(), []))
        found[-1][1].append(line)
    return found


def template_settings():
    """{section: [(key, its lines in TEMPLATE: the comments just over it and the line itself)]}."""
    settings = {}
    for section, lines in sections(TEMPLATE)[1:]:
        settings[section], pending = [], []
        for line in lines[1:]:
            if not line.strip():
                pending = []
                continue
            pending.append(line)
            if m := SETTING.match(line):
                settings[section].append((m[1], pending))
                pending = []
    return settings


def with_missing(text):
    """The settings file's text with the settings it doesn't mention (set or commented out)
    added, commented out as in TEMPLATE: in their section, or in a new one at the end. The
    rest stays as it was written. The same text if nothing is missing."""
    parts = sections(text)
    present = {}
    for section, lines in parts:
        present.setdefault(section, set()).update(m[1] for line in lines if (m := SETTING.match(line)))
    added = False
    for section, settings in template_settings().items():
        missing = [b for key, b in settings if key not in present.get(section, set())]
        if not missing:
            continue
        added = True
        lines = [line for b in missing for line in b]
        place = next((i for i, (name, _) in reversed(list(enumerate(parts))) if name == section), None)
        if place is None:
            parts.append((section, ["", f"[{section}]", *lines]))
        else:
            body = parts[place][1]
            while body and not body[-1].strip():  # after its last line, before the blank ones
                body.pop()
            body += lines + [""]
    if not added:
        return text
    out = "\n".join(line for _, lines in parts for line in lines)
    return out.rstrip("\n") + "\n"


def ensure():
    """Write the settings file (everything commented out) if it isn't there, or add to it the
    settings a newer song-wizard has that it doesn't mention (commented out, so nothing changes).
    True if it was written."""
    if CONFIG_PATH.exists():
        try:
            text = CONFIG_PATH.read_text(encoding="utf-8")
            new = with_missing(text)
            if new != text:
                tomllib.loads(new)  # never leave it broken
                write_text(new)
        except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError):
            pass  # a file that can't be read or fixed: load() says what's wrong with it
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
