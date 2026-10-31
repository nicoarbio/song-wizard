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
        out = os.path.join(folder, f"{command}.txt")
        lines = {}
        if os.path.exists(out):
            with open(out, encoding="utf-8") as f:
                for line in f:
                    if line.startswith("#") or "\t" not in line:
                        continue
                    name, text = line.rstrip("\n").split("\t", 1)
                    lines[name] = text
        lines.update(new)
        with open(out, "w", encoding="utf-8") as f:
            f.write(HEADER.format(command=command, date=f"{datetime.datetime.now():%Y-%m-%d %H:%M}"))
            for name in sorted(lines):
                f.write(f"{name}\t{lines[name]}\n")
        written.append(out)
    return written
