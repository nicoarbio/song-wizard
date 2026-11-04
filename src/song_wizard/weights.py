"""Model weights song-wizard downloads itself (the chord and vocal-pitch models): once, from a fixed
address, and used only if their SHA-256 matches what's written here."""

import hashlib
import os
import shutil
import sys
import urllib.request

from . import __version__
from .paths import MODELS_DIR


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def fetch(url, expected, filename, what, size, folder=None):
    """The file, downloaded and checked the first time. Exits if it can't be had or doesn't match."""
    folder = folder or MODELS_DIR
    path = folder / filename
    if path.is_file() and sha256(path) == expected:
        return path
    folder.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".part")
    print(f"Downloading the {what} ({size}, once)...", flush=True)
    try:
        request = urllib.request.Request(url, headers={"User-Agent": f"song-wizard/{__version__}"})
        with urllib.request.urlopen(request, timeout=60) as response, open(tmp, "wb") as f:
            shutil.copyfileobj(response, f)
    except OSError as e:
        tmp.unlink(missing_ok=True)
        sys.exit(f"Couldn't download the {what} ({getattr(e, 'reason', e)}). Try again in a while.")
    if sha256(tmp) != expected:
        tmp.unlink(missing_ok=True)
        sys.exit(f"The {what} downloaded isn't the expected one (its SHA-256 doesn't match), so it wasn't "
                 "used. Try again later; if it keeps happening, report it (song-wizard report).")
    os.replace(tmp, path)
    return path
