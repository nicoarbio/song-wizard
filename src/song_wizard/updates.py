"""Versions of song-wizard: the ones published (a "vX.Y.Z" tag on GitHub for each), whether
there's a newer one, and installing the newest or a given one.

The tags are read the way git does (the repository's ref list over HTTPS), so it needs neither
git (on a Mac, calling it can pop up an installer) nor GitHub's API (which limits how often it
can be asked)."""

import re
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

from . import __version__

REPO = "https://github.com/nicoarbio/song-wizard"
REFS = f"{REPO}.git/info/refs?service=git-upload-pack"
TAG = re.compile(rb"refs/tags/v(\d+\.\d+\.\d+)(?!\^)")
# Back to the newest from a version older than 0.15, whose upgrade doesn't know about tags.
BACK_TO_NEWEST = f"uv tool install --force git+{REPO}"


def parse(version):
    """'0.13.2' -> (0, 13, 2); anything else -> None."""
    return tuple(int(p) for p in version.split(".")) if re.fullmatch(r"\d+(\.\d+)*", version or "") else None


def versions(timeout=8):
    """The published versions, oldest first; None if they can't be read (no internet, say)."""
    request = urllib.request.Request(REFS, headers={"User-Agent": "git/2.0 (song-wizard)"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            refs = response.read(2_000_000)
    except (OSError, ValueError):
        return None
    found = {m.decode() for m in TAG.findall(refs)}
    return sorted(found, key=parse) or None


def latest(timeout=8):
    """The newest published version, or None if it can't be told."""
    found = versions(timeout)
    return found[-1] if found else None


def newer(version, than=None):
    a, b = parse(version), parse(than or __version__)
    return bool(a and b and a > b)


def source():
    """Where this song-wizard was installed from: "git", "directory" (a copy of the code, for
    whoever works on it), or None if it can't be told (not installed with uv tool)."""
    try:
        tools = subprocess.run(["uv", "tool", "dir"], capture_output=True, text=True, check=True).stdout.strip()
        receipt = (Path(tools) / "song-wizard" / "uv-receipt.toml").read_text()
    except (OSError, subprocess.CalledProcessError):
        return None
    if re.search(r"\bdirectory\s*=", receipt):
        return "directory"
    return "git" if re.search(r"\bgit\s*=", receipt) else None


def uv(*args):
    if not shutil.which("uv"):
        sys.exit("uv is missing; reinstall song-wizard following the README.")
    print("$ uv " + " ".join(args), flush=True)
    return subprocess.run(["uv", *args]).returncode


def install(version):
    """Install that published version (and the newest of what it uses). Returns uv's exit code."""
    return uv("tool", "install", "--force", "--upgrade", f"song-wizard @ git+{REPO}@v{version}")


def check():
    found = latest()
    if found is None:
        print(f"song-wizard {__version__}. Couldn't check for a newer one (no internet?).")
    elif newer(found):
        print(f"song-wizard {__version__}; {found} is out: song-wizard upgrade installs it.")
    else:
        print(f"song-wizard {__version__}: up to date.")


def show():
    found = versions()
    if not found:
        sys.exit("Couldn't read the published versions (no internet?).")
    print(f"Published versions (yours: {__version__}):")
    for v in reversed(found):
        print(f"  {v}" + ("  ← installed" if v == __version__ else "") + ("  (newest)" if v == found[-1] else ""))
    print("song-wizard upgrade installs the newest; song-wizard upgrade --to VERSION, another one.")


def upgrade():
    """The newest published version if there's a newer one; else, the newest of what it uses
    (yt-dlp above all: sites change and downloads can stop working until it's updated)."""
    found = latest()
    if source() == "directory":
        # Installed from a copy of the code: upgrading means taking that copy again.
        print("Installed from a folder with the code: reinstalling from it.")
        return uv("tool", "upgrade", "--reinstall", "song-wizard")
    if found and newer(found):
        print(f"song-wizard {__version__} → {found}")
        return install(found)
    print((f"song-wizard {__version__} is the newest" if found else "Couldn't check for a newer song-wizard (no internet?)")
          + "; updating what it uses.")
    return uv("tool", "upgrade", "song-wizard")


def to(version):
    version = version.lstrip("v")
    found = versions()
    if found is None:
        sys.exit("Couldn't read the published versions (no internet?).")
    if version not in found:
        sys.exit(f"There's no version {version}. song-wizard upgrade --list shows them.")
    if version == __version__:
        print(f"song-wizard {version} is the one installed.")
        return 0
    if source() == "directory":
        print("Note: this was installed from a folder with the code; now it'll come from GitHub "
              "(uv tool install --reinstall FOLDER goes back to the folder).")
    code = install(version)
    if code == 0 and newer(found[-1], version) and parse(version) < (0, 15, 0):
        print(f"Versions before 0.15 can't move to a newer one by themselves; to come back to the newest: {BACK_TO_NEWEST}")
    return code
