"""Songs numbered like a playlist's: "001 - Artist - Title". A song added by hand to a playlist's
folder takes the number after the last one, and songs downloaded later go on from there (not from
their place in the site's playlist, which may clash with the folder's own order)."""

import os
import subprocess
import time
from pathlib import Path

from . import song
from .rename import NUMBER

# A song changed this recently may still be copying in (or syncing): it's left for later.
SETTLING = 30


def songs(folder):
    """{song: its main file} of the songs in a folder of songs."""
    return {here.name: song.main_in(here) for here in song.songs_in(folder)}


def number_of(base):
    match = NUMBER.match(base)
    return int(match.group(0)[:-3]) if match else None


def highest(folder):
    """The last number in the folder (0 if none) and how many digits the numbers have."""
    numbered = [NUMBER.match(b).group(0)[:-3] for b in songs(folder) if NUMBER.match(b)]
    return max((int(n) for n in numbered), default=0), max((len(n) for n in numbered), default=3)


def name(path, number=None, digits=3, own=True):
    """Name the song at path by its data ("Artist - Title"; without a title, the name it has),
    with this number in front, or the one it has. Its stems, versions and results follow. own:
    song-wizard got it (downloaded it), so it carries its mark. Returns where it ended up."""
    from . import rename, tags

    from . import layout
    path = Path(path)
    if path.is_file() and not song.is_song(path.parent):
        path = layout.fold_one(path)
    path = song.main(path)
    current = path.parent.name
    has = NUMBER.match(current)
    plain = current[has.end():] if has else current
    new = tags.name_for(tags.read(path)) or plain
    prefix = f"{number:0{digits}d} - " if number is not None else (has.group(0) if has else "")
    target = prefix + new
    final = path
    if target != current:
        try:
            final = rename.run(str(path), target)
        except SystemExit as e:
            if number is None or target == prefix + plain:
                print(f"  {path.name}: kept its name ({e.code})")
            else:
                # The name its data gives is taken: at least the number.
                try:
                    final = rename.run(str(path), prefix + plain)
                except SystemExit as e:
                    print(f"  {path.name}: kept its name ({e.code})")
    if own and final.is_file():
        for f in tags.song_files(final):
            tags.stamp(f, f)
    return final


def tidy(folder, wav=False):
    """Number the songs added by hand to a playlist's folder after the last one, in the order
    they came, named by their data, with their .wav if the playlist keeps them. Returns them."""
    from . import layout
    folder = Path(folder)
    if layout.busy(folder):  # a download is bringing songs in: it numbers them itself
        return []
    layout.fold(folder, settle=SETTLING)
    found = songs(folder)
    now = time.time()
    loose = []
    for base, main in found.items():
        if NUMBER.match(base):
            continue
        try:
            changed = main.stat().st_mtime
        except OSError:
            continue
        if now - changed >= SETTLING:
            loose.append((changed, base.lower(), str(main)))
    if not loose:
        return []
    last, digits = highest(folder)
    done = []
    for i, (_, _, main) in enumerate(sorted(loose), 1):
        print(f"Numbering {Path(main).name}, added by hand:", flush=True)
        final = name(main, last + i, digits, own=False)
        if wav and final.suffix.lower() != ".wav" and not final.with_suffix(".wav").exists():
            made = subprocess.run(["ffmpeg", "-nostdin", "-n", "-loglevel", "error", "-i", str(final),
                                   str(final.with_suffix(".wav"))], capture_output=True, text=True)
            if made.returncode == 0:
                from . import tags
                tags.stamp(str(final.with_suffix(".wav")), str(final))
            else:
                print(f"  couldn't make its .wav: {made.stderr.strip()[-200:]}")
        done.append(final)
    return done


def reorder(folder, order):
    """Number the folder's songs in this order (songs or their file names); the ones not given
    go after, as they were. Each song's stems, versions, results, lyrics and REAPER project
    follow it."""
    import contextlib
    import io

    from . import rename
    from .audio import die

    folder = Path(folder)
    if not folder.is_dir():
        die(f"{folder}: no such folder.")
    found = songs(folder)
    wanted = []
    for item in order:
        item = Path(item)
        # A song's name, its folder or any of its files.
        if item.is_absolute():
            inside = item if item.parent.resolve() == folder.resolve() else item.parent
            if inside.parent.resolve() != folder.resolve():
                die(f"{item}: it isn't in {folder}.")
            base = inside.name
        else:
            base = item.parts[0] if item.parts else ""
            base = base if base in found else os.path.splitext(base)[0]
        if base not in found:
            die(f"{item}: not a song in {folder}.")
        if base not in wanted:
            wanted.append(base)
    rest = sorted((b for b in found if b not in wanted),
                  key=lambda b: (number_of(b) is None, number_of(b) or 0, b.lower()))
    final = wanted + rest
    last, digits = highest(folder)
    digits = max(digits, len(str(len(final))))
    plain = lambda b: b[NUMBER.match(b).end():] if NUMBER.match(b) else b
    target = {b: f"{i:0{digits}d} - {plain(b)}" for i, b in enumerate(final, 1)}
    moving = [b for b in final if target[b] != b]
    if not moving:
        print("They're already in that order.")
        return
    # In two steps, so two songs can swap numbers: first each one out of the way (to a number no
    # song has), then to its place.
    spare = max(last, len(final)) + 1
    steps = [(b, f"{spare + i:0{digits}d} - {plain(b)}") for i, b in enumerate(moving)]
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            for b, aside in steps:
                rename.run(str(folder / b), aside)
            for b, aside in steps:
                rename.run(str(folder / aside), target[b])
    except SystemExit as e:
        die(f"Stopped halfway, some songs have their new number and others don't ({e.code}). "
            "Running it again finishes it.")
    for b in moving:
        print(f"  {b}  ->  {target[b]}")
    print(f"{len(moving)} song{'s' if len(moving) != 1 else ''} renumbered in {folder.name}.")
