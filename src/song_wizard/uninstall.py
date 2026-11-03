"""song-wizard uninstall: remove song-wizard and what it keeps outside the music folder (the
separation models, the record of downloads, the logs and the settings), saying first what goes,
how much it takes, and what stays."""

import os
import shutil
import subprocess
import sys
from pathlib import Path

from . import config, paths, system

YES = ("y", "yes", "s", "si", "sí")


def size(path):
    """Bytes under a folder (or of a file); 0 if it isn't there."""
    path = Path(path)
    if path.is_file():
        return path.stat().st_size
    total = 0
    for root, _dirs, files in os.walk(path):
        for name in files:
            try:
                total += (Path(root) / name).lstat().st_size
            except OSError:
                pass
    return total


def human(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit in ("B", "KB") else f"{n:.1f} {unit}"
        n /= 1024


def program_dir():
    """song-wizard's own folder in uv's tools (its Python and everything it uses), or None if
    it wasn't installed with uv tool."""
    try:
        tools = subprocess.run(["uv", "tool", "dir"], capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None
    folder = Path(tools) / "song-wizard"
    return folder if folder.is_dir() else None


def data_places():
    """What song-wizard keeps outside the music folder: (what it is, path), only what exists."""
    places = [
        ("the separation models", paths.MODELS_DIR),
        ("the record of downloaded playlists", paths.ARCHIVE_DIR),
        ("everything else song-wizard keeps (logs, the interface's and REAPER's state)", paths.DATA_DIR),
        ("the settings", config.CONFIG_PATH.parent),
    ]
    return [(what, path) for what, path in places if path.exists()]


def ask(question, default_yes=False):
    if not sys.stdin.isatty():
        return default_yes
    answer = input(question).strip().lower()
    return answer in YES if answer else default_yes


def run(keep_data=False, yes=False):
    places = [] if keep_data else data_places()
    program = program_dir()
    if not places and not program:
        print("song-wizard keeps nothing outside the music folder and isn't installed with uv tool: "
              "nothing to remove.")
        return

    print("This removes:")
    inside_data = [p for _, p in places if p != paths.DATA_DIR]
    for what, path in places:
        # The data folder holds the models and the archives: its size is what's left besides them.
        n = size(path) - (sum(size(p) for p in inside_data if paths.DATA_DIR in p.parents) if path == paths.DATA_DIR else 0)
        print(f"  - {what}: {system.shown_path(path)} ({human(n)})")
    if program:
        print(f"  - song-wizard itself, with its own Python and everything it uses: {system.shown_path(program)} "
              f"({human(size(program))})")
    print("\nIt doesn't touch:")
    print(f"  - your music ({system.shown_path(paths.music_dir())}): songs, stems, versions, key.txt, bpm.txt, "
          "click.txt, lyrics and REAPER projects stay")
    print("  - ffmpeg, rubberband, deno or uv: other programs may use them (if you don't, uninstall them "
          "yourself: sudo apt remove / brew uninstall)")
    print("  - uv's download cache, shared with whatever else you install with uv (uv cache clean empties it)")
    if keep_data:
        print("  - the models, the record of downloads and the settings (--keep-data): installing it again "
              "picks them up")
    elif paths.ARCHIVE_DIR.exists() and any(paths.ARCHIVE_DIR.iterdir()):
        print("\nWithout the record of downloads, if you install song-wizard again, looking for new songs "
              "in a playlist would download all of it again.")

    if not yes:
        if not sys.stdin.isatty():
            sys.exit("\nNot removing anything without asking: add --yes to do it.")
        if not ask("\nRemove it? [y/N] "):
            print("Nothing was removed.")
            return

    from . import ui
    if ui.running() and not ui.stop(yes=yes):
        print("Nothing was removed.")
        return

    if not keep_data:
        restore_reaper(yes)
        for what, path in places:
            if path.exists():
                shutil.rmtree(path, ignore_errors=True) if path.is_dir() else path.unlink()
                print(f"Removed {what}.")

    if program:
        print("Uninstalling song-wizard:", flush=True)
        # Last, and in uv's place: this very program lives in the folder it removes.
        os.execvp("uv", ["uv", "tool", "uninstall", "song-wizard"])
    else:
        print("song-wizard isn't installed with uv tool here (it runs from a copy of the code): "
              "delete that folder yourself if you want.")


def restore_reaper(yes):
    """If song-wizard changed REAPER's takes setting, offer to put it back as it was."""
    from . import reaper
    try:
        now = reaper.setting()
    except OSError:
        return
    if not now["changed"]:
        return
    print("\nsong-wizard changed a REAPER setting (Preferences > Recording > \"Recorded filenames\") so takes "
          f"go with their song. Before it was: {reaper.shown(now['before'])}.")
    if not (yes or ask("Put it back as it was? [Y/n] ", default_yes=True)):
        print("Left as it is.")
        return
    done = reaper.restore()
    if done == "running":
        print("REAPER is open, so it couldn't be put back (it rewrites its settings when it closes). "
              "Close it and change it in its Preferences.")
    elif done == "restored":
        print("Put back REAPER's setting.")
