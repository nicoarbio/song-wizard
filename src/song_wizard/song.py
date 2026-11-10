"""What a song is on disk: a folder named after it, with everything that goes with it inside.

    Showww dic-2026/                     a playlist (or Singles, or any folder of songs)
      003 - Cryin'/                      the song's folder
        003 - Cryin'.opus                its main file: the folder's name (other formats too: .wav, .mp3)
        drums.opus  no drums.opus        stems, versions and clicks, named by what they are
        80%.opus  drums +2.opus          ("drums" made 80 % slower is "drums 80%")
        click 120 BPM 4-4.wav
        record 2026-11-01 19-05-12.wav   takes recorded in REAPER
        key.txt  tempo.txt               what was detected or set by hand
        lyrics.json  chords.json  notes.json  drums.json
        003 - Cryin'.rpp                 its REAPER project (REAPER keeps its .reapeaks here too)

Everything else in song-wizard asks this module where a song's files are. The layout before
0.42.0 (all songs loose in their playlist's folder) is known only to layout.py, which moves it here.
"""

import os
import re
from pathlib import Path

from .audio import AUDIO_EXTS, MAIN_FORMATS, die

# One part of a generated file's name: a stem, a version (transposed, at another speed), a click.
STEMS = r"(?:no )?(?:vocals|drums|bass|guitar|piano)|other|kick|snare|toms|hihat|ride|crash|drums rest"
PITCH = r"[+-]\d+(?:\.\d+)?"
SPEED = r"\d+(?:\.\d+)?%(?:, [+-]\d+(?:\.\d+)?)?"
CLICK = r"click \d+(?:\.\d+)? BPM \d+-\d+(?: x\d+)?"
PART = re.compile(rf"(?:drums rest|{STEMS}|{SPEED}|{PITCH}|{CLICK})(?= |$)")
STEM = re.compile(rf"^(?:{STEMS})$")
VERSION = re.compile(rf"^(?:{SPEED}|{PITCH})$")
SPEED_PART = re.compile(r"^(\d+(?:\.\d+)?)%")
# Takes recorded in REAPER ("-001"... when several tracks record at once).
TAKE = re.compile(r"^record \d{4}-\d\d-\d\d \d\d-\d\d-\d\d(?:-\d+)?$")

# The song's data, in its folder.
DATA = {"key": "key.txt", "tempo": "tempo.txt", "lyrics": "lyrics.json", "chords": "chords.json",
        "notes": "notes.json", "drums": "drums.json"}
# Files made to take elsewhere (to print, to send, to open in REAPER) keep the song's name:
# "<song>.lyrics.html", "<song>.drums.mid", "<song>.rpp"...
EXPORTS = (".lyrics.html", ".chords.html", ".bass.html", ".drums.html", ".drums.mid", ".rpp", ".rpp-bak")
# REAPER's waveform cache, next to each audio file it opened: "drums.opus.reapeaks".
PEAKS = ".reapeaks"


class OldLayout(Exception):
    """A song still loose in its playlist's folder, as before 0.42.0."""


def parts(name):
    """The parts a generated file's name is made of: "drums 80%.opus" -> ["drums", "80%"];
    "record ...wav" -> ["record ..."]; None if it isn't one ("003 - Cryin'.opus")."""
    stem = os.path.splitext(os.path.basename(name))[0]
    if TAKE.match(stem):
        return [stem]
    found, at = [], 0
    while at < len(stem):
        match = PART.match(stem, at)
        if not match:
            return None
        found.append(match[0])
        at = match.end() + 1
    return found or None


def kind(name):
    """What a file in a song's folder is: "take", "click", "version" (transposed or at another
    speed, a stem's too), "stem", or None (the song itself, in any format, or something else)."""
    found = parts(name)
    if not found:
        return None
    if TAKE.match(found[0]):
        return "take"
    if found[0].startswith("click "):
        return "click"
    if any(VERSION.match(p) for p in found):
        return "version"
    return "stem"


def speed_of(name):
    """How much faster than the song a file plays (0.8 for "drums 80%"), 1 if it isn't sped."""
    factor = 1.0
    for p in parts(name) or []:
        if match := SPEED_PART.match(p):
            factor *= float(match[1]) / 100
    return factor


def rank(name):
    ext = os.path.splitext(name)[1].lower()
    return MAIN_FORMATS.index(ext) if ext in MAIN_FORMATS else len(MAIN_FORMATS)


def main_in(folder):
    """The song's main file if this folder is a song's: "<folder name>.<ext>", in the format
    shown first (an .opus over the .wav made from it). None otherwise."""
    folder = Path(folder)
    try:
        names = [n for n in os.listdir(folder)
                 if os.path.splitext(n)[0] == folder.name and os.path.splitext(n)[1].lower() in AUDIO_EXTS]
    except OSError:
        return None
    names = [n for n in names if (folder / n).is_file()]
    return folder / min(names, key=rank) if names else None


def is_song(folder):
    return main_in(folder) is not None


def folder_of(path):
    """The song's folder for any of its files (or the folder itself). Raises OldLayout for a
    song loose in a folder of songs, and LookupError for anything else."""
    path = Path(os.path.abspath(path))
    if path.is_dir():
        if is_song(path):
            return path
        raise LookupError(f"{path}: not a song's folder")
    if is_song(path.parent):
        return path.parent
    if os.path.splitext(path.name)[1].lower() in AUDIO_EXTS:
        raise OldLayout(str(path.parent))
    raise LookupError(f"{path}: not a song's file")


def old_layout_message(folder):
    return (f"{folder}: its songs are still loose in the folder (song-wizard keeps each song in a folder of "
            f'its own since 0.42.0). Run "song-wizard tidy {folder}" to put them in place.')


def folder(path):
    """folder_of, or exits saying why (for the commands)."""
    try:
        return folder_of(path)
    except OldLayout as e:
        die(old_layout_message(e.args[0]))
    except LookupError as e:
        die(str(e.args[0]))


def main(path):
    """The song's main file, for any of its files."""
    return main_in(folder(path))


def name(path):
    """The song's name ("003 - Cryin'") for any of its files."""
    return folder(path).name


def data(path, what):
    """Where one piece of the song's data goes (see DATA): "key", "tempo", "lyrics"..."""
    return folder(path) / DATA[what]


def export(path, suffix):
    """A file made to take elsewhere, with the song's name: export(song, ".drums.mid")."""
    here = folder(path)
    return here / f"{here.name}{suffix}"


def made(source, part, ext=None):
    """Where a file made from this one goes: made("…/drums.opus", "80%") -> "…/drums 80%.opus";
    from the song itself, just "80%.opus". ext: the settings' format for stems and versions."""
    from .audio import stem_ext

    source = Path(source)
    before = parts(source.name)
    stem = " ".join([*before, part]) if before and kind(source.name) != "take" else part
    return folder(source) / f"{stem}{ext or stem_ext()}"


def stem(path, part):
    """The song's file for one part ("bass"), in the format the settings choose first, then the
    others (older songs have .wav). None if there isn't one."""
    from .audio import stem_ext

    here = folder(path)
    for ext in dict.fromkeys([stem_ext(), ".opus", ".wav", ".mp3"]):
        found = here / f"{part}{ext}"
        if found.is_file():
            return found
    return None


def audio_files(path, takes=False):
    """The song's audio files: it (in every format), its stems, versions and clicks; and with
    takes, the takes recorded in REAPER too."""
    here = folder(path)
    return [here / n for n in sorted(os.listdir(here))
            if os.path.splitext(n)[1].lower() in AUDIO_EXTS and (here / n).is_file()
            and (takes or kind(n) != "take")]


def own_files(path):
    """The song's main file in every format ("003 - Cryin'.opus", "003 - Cryin'.wav")."""
    here = folder(path)
    return sorted((p for p in audio_files(here) if p.stem == here.name), key=lambda p: rank(p.name))


def songs_in(container):
    """The songs' folders in a folder of songs (a playlist, Singles...), by name."""
    try:
        found = [p for p in Path(container).iterdir() if p.is_dir() and not p.name.startswith(".") and is_song(p)]
    except OSError:
        return []
    return sorted(found, key=lambda p: p.name.lower())


def expand(paths):
    """The songs' main files for what was named: a song's file is its song; a song's folder too;
    a folder of songs, every song in it. Exits on a folder in the layout before 0.42.0."""
    seen = []
    for p in paths:
        p = Path(os.path.abspath(p))
        if p.is_dir() and not is_song(p):
            from . import layout
            if layout.needed(p):
                die(old_layout_message(p))
            seen += [main_in(f) for f in songs_in(p)]
        elif p.exists():
            seen.append(main(p))
        else:
            print(f"  skipping {p}: not found")
    return list(dict.fromkeys(seen))


def files(paths):
    """Like expand, but a song's file named on its own stays that file (a stem, say)."""
    out = []
    for p in paths:
        if Path(p).is_file():
            folder(p)  # exits on a song loose in its folder
            out.append(Path(os.path.abspath(p)))
        else:
            out += expand([p])
    return list(dict.fromkeys(out))
