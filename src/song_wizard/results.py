"""Results of key and bpm, saved as text next to the songs so they don't get lost in the console.

One file per folder ("key.txt", "bpm.txt"), one line per song: "file name<TAB>result". Running
again on some songs only replaces their lines.
"""

import datetime
import os
from collections import defaultdict

HEADER = "# song-wizard {command}, updated {date}. One line per song: file name, tab, result.\n"


def save(command, results):
    """results: [(song path, result text)]. Returns the files written."""
    by_folder = defaultdict(dict)
    for path, text in results:
        by_folder[os.path.dirname(os.path.abspath(path))][os.path.basename(path)] = text

    written = []
    for folder, new in by_folder.items():
        lines = read(folder, command)
        lines.update(new)
        written.append(write(folder, command, lines))
    return written


def rename(folder, command, names):
    """Follow renamed files ({old name: new name}). Returns whether anything changed."""
    lines = read(folder, command)
    if not any(name in lines for name in names):
        return False
    write(folder, command, {names.get(name, name): text for name, text in lines.items()})
    return True


def read(folder, command):
    """{file name: result} from <folder>/<command>.txt; empty if there's none."""
    lines = {}
    path = os.path.join(folder, f"{command}.txt")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                if line.startswith("#") or "\t" not in line:
                    continue
                name, text = line.rstrip("\n").split("\t", 1)
                lines[name] = text
    return lines


def write(folder, command, lines):
    path = os.path.join(folder, f"{command}.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write(HEADER.format(command=command, date=f"{datetime.datetime.now():%Y-%m-%d %H:%M}"))
        for name in sorted(lines):
            f.write(f"{name}\t{lines[name]}\n")
    return path
