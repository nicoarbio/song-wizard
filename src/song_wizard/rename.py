"""Rename a song and everything made from it: its other formats, stems and versions, its lyrics,
and its lines in key.txt and bpm.txt."""

import os
import re

from . import results
from .audio import AUDIO_EXTS, base_of, die

# Not allowed in file names on Windows (where the music folder is on WSL), nor "/" anywhere.
FORBIDDEN = set('\\/:*?"<>|')
NUMBER = re.compile(r"^\d+ - ")


# Files that go with a song without being audio: its lyrics and their printable page.
COMPANIONS = (".lyrics.json", ".lyrics.html")


def group(folder, base):
    """Every file in the folder that belongs to this song: its audio files and its lyrics."""
    return sorted(n for n in os.listdir(folder)
                  if ((os.path.splitext(n)[1].lower() in AUDIO_EXTS and base_of(n) == base)
                      or n in {base + c for c in COMPANIONS})
                  and os.path.isfile(os.path.join(folder, n)))


def new_base(old, new):
    """The new name, cleaned up. Keeps the "001 - " numbering unless the new name has its own."""
    new = new.strip()
    if os.path.splitext(new)[1].lower() in AUDIO_EXTS:
        new = os.path.splitext(new)[0].strip()
    bad = sorted(set(new) & FORBIDDEN)
    if bad:
        die(f'The name can\'t have {" ".join(bad)} (Windows doesn\'t allow them in file names).')
    if not new or new.endswith("."):
        die("The new name can't be empty or end with a dot.")
    if base_of(new + ".wav") != new:
        die(f'"{new}" looks like a file song-wizard makes (a stem or a version); pick another name.')
    number = NUMBER.match(old)
    if number and not NUMBER.match(new):
        new = number.group(0) + new
    return new


def plan(path, new):
    """[(old name, new name)] for the song at path, or exits explaining why not."""
    folder, name = os.path.split(os.path.abspath(path))
    if not os.path.isfile(path):
        die(f"{path}: not found")
    old = base_of(name)
    new = new_base(old, new)
    if new == old:
        die("That's already its name.")
    renames = [(n, new + n[len(old):]) for n in group(folder, old)]
    sources = {os.path.join(folder, n) for n, _ in renames}
    clashes = []
    for _, target in renames:
        target_path = os.path.join(folder, target)
        # A case-only change ("song" -> "Song") on a case-insensitive disk finds the file itself.
        if os.path.exists(target_path) and not any(os.path.samefile(target_path, s) for s in sources):
            clashes.append(target)
    if clashes:
        die("Nothing renamed: these already exist:\n" + "\n".join(f"  {c}" for c in clashes))
    return folder, renames


def run(path, new):
    folder, renames = plan(path, new)
    done = []
    try:
        for old, target in renames:
            os.rename(os.path.join(folder, old), os.path.join(folder, target))
            done.append((old, target))
    except OSError as e:
        for old, target in reversed(done):
            os.rename(os.path.join(folder, target), os.path.join(folder, old))
        die(f"Nothing renamed: {e}")
    for old, target in renames:
        print(f"  {old}  ->  {target}")
    for command in ("key", "bpm", "click"):
        if results.rename(folder, command, dict(renames)):
            print(f"  updated {command}.txt")
