"""Rename a song: its folder, its main file (in every format), the files made to take elsewhere
("<song>.rpp", "<song>.drums.mid"...) and REAPER's peaks of them. Stems and versions keep their
short names ("drums.opus"), so they don't move."""

import os
import re

from . import song
from .audio import die

# Not allowed in file names on Windows (where the music folder is on WSL), nor "/" anywhere.
FORBIDDEN = set('\\/:*?"<>|')
NUMBER = re.compile(r"^\d+ - ")


def group(here, base=None):
    """The files in the song's folder named after it: [(name, the rest after the song's name)]."""
    base = base or here.name
    return [(n, n[len(base):]) for n in sorted(os.listdir(here))
            if n.startswith(base + ".") and (here / n).is_file()]


def new_base(old, new):
    """The new name, cleaned up. Keeps the "001 - " numbering unless the new name has its own."""
    new = new.strip()
    from .audio import AUDIO_EXTS
    if os.path.splitext(new)[1].lower() in AUDIO_EXTS:
        new = os.path.splitext(new)[0].strip()
    bad = sorted(set(new) & FORBIDDEN)
    if bad:
        die(f'The name can\'t have {" ".join(bad)} (Windows doesn\'t allow them in file names).')
    if not new or new.endswith("."):
        die("The new name can't be empty or end with a dot.")
    if song.parts(new + ".wav"):
        die(f'"{new}" looks like a file song-wizard makes (a stem or a version); pick another name.')
    number = NUMBER.match(old)
    if number and not NUMBER.match(new):
        new = number.group(0) + new
    return new


def plan(path, new):
    """(song folder, [(old name, new name)] inside it, old name, new name), or exits saying why."""
    if not os.path.exists(path):
        die(f"{path}: not found")
    here = song.folder(path)
    old = here.name
    new = new_base(old, new)
    if new == old:
        die("That's already its name.")
    target = here.with_name(new)
    # A case-only change ("song" -> "Song") on a case-insensitive disk finds the folder itself.
    if target.exists() and not os.path.samefile(target, here):
        die(f"Nothing renamed: {target} already exists.")
    renames = [(n, new + rest) for n, rest in group(here)]
    # REAPER's caches of them, if it keeps them in a "peaks" folder.
    if (here / "peaks").is_dir():
        renames += [(f"peaks/{n}", f"peaks/{new}{rest}") for n, rest in group(here / "peaks", here.name)]
    return here, renames, old, new


def run(path, new):
    """Returns the song's main file in its new place."""
    here, renames, old_base, new_base = plan(path, new)
    done = []
    target = here.with_name(new_base)
    try:
        for old, name in renames:
            os.rename(here / old, here / name)
            done.append((old, name))
        os.rename(here, target)
    except OSError as e:
        for old, name in reversed(done):
            os.rename(here / name, here / old)
        die(f"Nothing renamed: {e}")
    print(f"  {here.name}/  ->  {target.name}/")
    for old, name in renames:
        print(f"    {old}  ->  {name}")
    # A REAPER project points to the song's files by name: point it to the new names.
    from . import reaper
    for _, name in renames:
        if name.lower().endswith((".rpp", ".rpp-bak")) and reaper.rename_inside(target / name, old_base, new_base):
            print(f"  updated the files {name} points to")
    return song.main_in(target)
