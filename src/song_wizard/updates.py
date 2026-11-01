"""Versions of song-wizard: the ones published (a "vX.Y.Z" tag on GitHub for each), whether
there's a newer one, and installing the newest or a given one.

The tags are read the way git does (the repository's ref list over HTTPS), so it needs neither
git (on a Mac, calling it can pop up an installer) nor GitHub's API (which limits how often it
can be asked).

A version can be retired (a bad bug, say) by listing it in retired.txt on the main branch, with
the reason: it's no longer offered, nor installed without --force, and whoever has it is told.
The tag stays, so history isn't rewritten."""

import re
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

from . import __version__

REPO = "https://github.com/nicoarbio/song-wizard"
REFS = f"{REPO}.git/info/refs?service=git-upload-pack"
RETIRED = "https://raw.githubusercontent.com/nicoarbio/song-wizard/main/retired.txt"
RETIRED_LINE = re.compile(r"^v?(\d+\.\d+\.\d+)\s*(.*?)\s*$")
TAG = re.compile(rb"refs/tags/v(\d+\.\d+\.\d+)(?!\^)")
# Back to the newest from a version older than 0.15, whose upgrade doesn't know about tags.
BACK_TO_NEWEST = f"uv tool install --force git+{REPO}"


def parse(version):
    """'0.13.2' -> (0, 13, 2); anything else -> None."""
    return tuple(int(p) for p in version.split(".")) if re.fullmatch(r"\d+(\.\d+)*", version or "") else None


def retired(timeout=8):
    """{version: why} for the retired versions; empty if the list can't be read (then nothing
    is held back: better than blocking upgrades)."""
    request = urllib.request.Request(RETIRED, headers={"User-Agent": f"song-wizard/{__version__}"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            text = response.read(200_000).decode("utf-8", "replace")
    except (OSError, ValueError):
        return {}
    return {m[1]: m[2] or "retired" for line in text.splitlines()
            if not line.lstrip().startswith("#") and (m := RETIRED_LINE.match(line.strip()))}


def offered(timeout=8):
    """(the published versions that aren't retired, oldest first, or None if they can't be read;
    {version: why} for the retired ones)."""
    found, held = versions(timeout), retired(timeout)
    return ([v for v in found if v not in held] if found else None), held


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
    """The newest version on offer (published and not retired), or None if it can't be told."""
    found, _ = offered(timeout)
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
    found, held = offered()
    found = found[-1] if found else None
    if __version__ in held:
        print(f"song-wizard {__version__} was retired: {held[__version__]}. "
              + (f"song-wizard upgrade moves to {found}." if found else ""))
    elif found is None:
        print(f"song-wizard {__version__}. Couldn't check for a newer one (no internet?).")
    elif newer(found):
        print(f"song-wizard {__version__}; {found} is out: song-wizard upgrade installs it.")
    else:
        print(f"song-wizard {__version__}: up to date.")


def show(everything=False):
    published, held = versions(), retired()
    if not published:
        sys.exit("Couldn't read the published versions (no internet?).")
    good = [v for v in published if v not in held]
    print(f"Published versions (yours: {__version__}):")
    for v in reversed(published if everything else good):
        print(f"  {v}" + ("  ← installed" if v == __version__ else "") + ("  (newest)" if good and v == good[-1] else "")
              + (f"  retired: {held[v]}" if v in held else ""))
    hidden = len(published) - len(good)
    if hidden and not everything:
        print(f"({hidden} retired version{'s' if hidden != 1 else ''} not shown: --list --all shows them.)")
    print("song-wizard upgrade installs the newest; song-wizard upgrade --to VERSION, another one.")


def upgrade():
    """The newest version on offer if there's a newer one (or if this one was retired, even if
    the one on offer is older); else, the newest of what it uses (yt-dlp above all: sites change
    and downloads can stop working until it's updated)."""
    good, held = offered()
    found = good[-1] if good else None
    if source() == "directory":
        # Installed from a copy of the code: upgrading means taking that copy again.
        print("Installed from a folder with the code: reinstalling from it.")
        return uv("tool", "upgrade", "--reinstall", "song-wizard")
    if found and (newer(found) or (__version__ in held and found != __version__)):
        if __version__ in held:
            print(f"song-wizard {__version__} was retired ({held[__version__]}).")
        print(f"song-wizard {__version__} → {found}")
        return install(found)
    print((f"song-wizard {__version__} is the newest" if found else "Couldn't check for a newer song-wizard (no internet?)")
          + "; updating what it uses.")
    return uv("tool", "upgrade", "song-wizard")


def to(version, force=False):
    version = version.lstrip("v")
    found, held = versions(), retired()
    if found is None:
        sys.exit("Couldn't read the published versions (no internet?).")
    if version not in found:
        sys.exit(f"There's no version {version}. song-wizard upgrade --list shows them.")
    if version in held and not force:
        sys.exit(f"Version {version} was retired: {held[version]}. --force installs it anyway.")
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
