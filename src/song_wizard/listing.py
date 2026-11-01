"""The library in the terminal: what the interface shows, folder by folder."""

from pathlib import Path

from . import results, system
from .paths import music_dir


def folder_path(root, folder):
    """Where a library folder is on disk ("@<place>/..." folders carry their place)."""
    if folder["location"]:
        return Path(system.local_path(folder["location"])) / folder["path"].partition("/")[2]
    return root / folder["path"]


def run(text=None, files=False):
    from .ui import library

    root = music_dir()
    text = (text or "").lower()
    shown = 0
    for folder in library(root):
        here = folder_path(root, folder)
        songs = [s for s in folder["songs"] if not text or text in s["name"].lower() or text in folder["name"].lower()]
        if text and not songs:
            continue
        playlist = f"  playlist: {folder['playlist']['title']}" if folder["playlist"] else ""
        print(f"\n{system.shown_path(here)}  ({len(folder['songs'])} song{'s' if len(folder['songs']) != 1 else ''}){playlist}")
        for song in songs:
            details = []
            hand = f" ({results.HAND})"
            if song["key"]:
                details.append(song["key"].split()[0] + (hand if song["key"].endswith(results.HAND) else ""))
            if song["bpm"]:
                details.append(song["bpm"].split("  ")[0] + (hand if song["bpm"].endswith(results.HAND) else ""))
            if song["click"]:
                c = song["click"]
                details.append(f"click {c['bpm']:.2f} BPM {c['meter']} from {c['first']:.3f} s")
            if song["files"] and not files:
                details.append(f"+{len(song['files'])} file{'s' if len(song['files']) != 1 else ''}")
            print(f"  {song['name']}" + (f"  ·  {'  ·  '.join(details)}" if details else ""))
            if files:
                for f in song["files"]:
                    print(f"      {f['name']}")
        if files and not text:
            for extra in folder["extras"]:
                print(f"  {extra['name']}")
        shown += 1
    if not shown:
        print("Nothing found." if text else f"No songs yet in {system.shown_path(root)}.")
