"""Delete songs or single files to the system's trash. A song goes with everything made from it
(other formats, stems, versions, clicks) and its lines in key.txt, bpm.txt and click.txt; a
downloaded song also leaves its playlist's archive, so looking for new songs brings it back."""

import os
import subprocess
import sys
from collections import defaultdict

from . import archives, results, system
from .audio import base_of, die
from .rename import group


def source_link(path):
    """The link a downloaded file came from (yt-dlp writes it in the "purl" tag), or None."""
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format_tags=purl:stream_tags=purl",
                          "-of", "default=nw=1:nk=1", path], capture_output=True, text=True)
    return next((l.strip() for l in out.stdout.splitlines() if l.strip()), None)


def plan(songs=(), files=()):
    """The files to delete: every file of each song, and each single file."""
    targets = []
    for path in songs:
        if not os.path.isfile(path):
            die(f"{path}: not found")
        folder = os.path.dirname(os.path.abspath(path))
        targets += [os.path.join(folder, n) for n in group(folder, base_of(os.path.basename(path)))]
    for path in files:
        if not os.path.isfile(path):
            die(f"{path}: not found")
        targets.append(os.path.abspath(path))
    return list(dict.fromkeys(targets))


def run(songs=(), files=(), yes=False):
    # A stem or a version named as a "song" is just that file.
    generated = [s for s in songs if base_of(os.path.basename(s)) != os.path.splitext(os.path.basename(s))[0]]
    songs = [s for s in songs if s not in generated]
    files = [*files, *generated]
    targets = plan(songs, files)
    if not targets:
        die("Nothing to delete.")
    print(f"These {len(targets)} files go to the trash:")
    for t in targets:
        print(f"  {t}")
    if not yes:
        if not sys.stdin.isatty():
            die("Not deleting without confirmation: add --yes.")
        if input("Delete them? [y/N] ").strip().lower() not in ("y", "yes", "s", "si", "sí"):
            print("Nothing deleted.")
            return
    # Whole songs leave their playlist's archive: read their links before they're gone. (A single
    # file deleted on its own, like an .mp3 copy, doesn't take the song with it.)
    links = {link for path in plan(songs=songs) for link in [source_link(path)] if link}
    try:
        system.trash(targets)
    except system.TrashError as e:
        die(f"Stopped: {e}. Nothing else was touched.")
    by_folder = defaultdict(set)
    for t in targets:
        by_folder[os.path.dirname(t)].add(os.path.basename(t))
    for folder, names in by_folder.items():
        for command in ("key", "bpm", "click"):
            if results.forget(folder, command, names):
                print(f"  updated {os.path.join(folder, command)}.txt")
    if links and (gone := archives.forget_sources(links)):
        print(f"  {gone} song{'s' if gone != 1 else ''} left the playlist archive: looking for new songs brings "
              f"{'them' if gone != 1 else 'it'} back")
    print(f"Moved {len(targets)} file{'s' if len(targets) != 1 else ''} to the trash.")
