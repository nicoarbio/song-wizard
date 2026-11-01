"""Whether there's a newer song-wizard: the version on GitHub's main branch (every change there
bumps it), compared with this one. Read from the published pyproject.toml, which needs no API
key and has no rate limit to speak of."""

import re
import urllib.request

from . import __version__

REMOTE = "https://raw.githubusercontent.com/nicoarbio/song-wizard/main/pyproject.toml"


def parse(version):
    """'0.13.2' -> (0, 13, 2); anything else -> None."""
    return tuple(int(p) for p in version.split(".")) if re.fullmatch(r"\d+(\.\d+)*", version or "") else None


def latest(timeout=5):
    """The newest published version, or None if it can't be told (no internet, say)."""
    request = urllib.request.Request(REMOTE, headers={"User-Agent": f"song-wizard/{__version__}"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            text = response.read(20_000).decode("utf-8", "replace")
    except (OSError, ValueError):
        return None
    match = re.search(r'^version\s*=\s*"([^"]+)"', text, re.M)
    return match[1] if match and parse(match[1]) else None


def newer(version, than=__version__):
    a, b = parse(version), parse(than)
    return bool(a and b and a > b)


def check():
    found = latest()
    if found is None:
        print(f"song-wizard {__version__}. Couldn't check for a newer one (no internet?).")
    elif newer(found):
        print(f"song-wizard {__version__}; {found} is out: song-wizard upgrade installs it.")
    else:
        print(f"song-wizard {__version__}: up to date.")
