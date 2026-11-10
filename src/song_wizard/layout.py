"""From the layout before 0.42.0 to a folder per song (see song.py), and back.

Before, a playlist's songs were loose in its folder with everything made from them:

    003 - Cryin'.opus  003 - Cryin' (drums).wav  003 - Cryin' (drums) (80%).wav
    003 - Cryin'.lyrics.json  003 - Cryin'.rpp  003 - Cryin' (drums).wav.reapeaks
    key.txt  bpm.txt  click.txt        (one line per file of the folder)

tidy() moves each song to its folder, with the short names ("drums.wav", "drums 80%.wav"), its
lines of key.txt into its key.txt and of bpm.txt and click.txt into one tempo.txt, and points its
REAPER project to the new names. All of it or nothing; what it did is kept in the folder
(.song-wizard-tidy.json), so undo() puts it back as it was. This module is the only one that knows
the old layout.
"""

import datetime
import json
import os
import re
import time
from pathlib import Path

from . import song
from .audio import AUDIO_EXTS, MAIN_FORMATS, die

# The old names: "Title (drums).wav", "Title (no drums).wav", "Title (+2).wav", "Title (80%).wav",
# "Title (80%, -2).wav", "Title (click 120 BPM 4-4).wav", "Title (record 2026-11-01 19-05-12).wav",
# and "(click)"/"(count-in)" from an early click command; "Click 120 BPM 4-4.wav" is no song's.
OLD = re.compile(r" \(((no )?(vocals|drums|bass|guitar|piano)|other|kick|snare|toms|hihat|ride|crash|drums rest|[+-]\d+(\.\d+)?|\d+(\.\d+)?%(, [+-]\d+(\.\d+)?)?|click( \d+(\.\d+)? BPM \d+-\d+( x\d+)?)?)\)( \(count-in\))?$"
                 r"| \(count-in\)$"
                 r"| \(record \d{4}-\d\d-\d\d \d\d-\d\d-\d\d\)(-\d+)?$"
                 r"|^Click \d+(\.\d+)? BPM \d+-\d+( x\d+)?$")
LOOSE_CLICK = re.compile(r"^Click \d+(\.\d+)? BPM \d+-\d+( x\d+)?$")
# Old companions: "<song><suffix>" -> its name in the song's folder (None: keeps the song's name).
COMPANIONS = {".lyrics.json": "lyrics.json", ".chords.json": "chords.json", ".notes.json": "notes.json",
              ".drums.json": "drums.json", **{e: None for e in song.EXPORTS}}
RESULTS = ("key", "bpm", "click")
RECORD = ".song-wizard-tidy.json"
PEAKS = song.PEAKS
# A file changed this recently may still be copying in (or syncing): it's left for later.
SETTLING = 30
# Left in a folder while a download works on it: the library doesn't fold or number its songs
# meanwhile (songs moved in from Singles come without a number, and looked added by hand). One
# older than this was left by a download that died.
BUSY = ".song-wizard-busy"
BUSY_FOR = 3 * 3600


def busy(folder):
    try:
        return time.time() - (Path(folder) / BUSY).stat().st_mtime < BUSY_FOR
    except OSError:
        return False


class working:
    """with working(folder): the folder is busy while the block runs."""

    def __init__(self, folder):
        # A folder that isn't there yet (a new playlist's) isn't one the library numbers.
        self.mark = Path(folder) / BUSY if folder and Path(folder).is_dir() else None

    def __enter__(self):
        if self.mark:
            try:
                self.mark.write_text("a download is working here\n")
            except OSError:
                self.mark = None
        return self

    def __exit__(self, *exc):
        if self.mark:
            self.mark.unlink(missing_ok=True)


def old_base(name):
    """'Title (drums) (80%).wav' -> 'Title'."""
    stem = os.path.splitext(name)[0]
    while (match := OLD.search(stem)) and match.start() > 0:
        stem = stem[:match.start()]
    return stem


def new_name(name, base):
    """A song's old file name -> its name in the song's folder ("Title (drums) (80%).wav" ->
    "drums 80%.wav"); a name it can't read keeps it."""
    stem, ext = os.path.splitext(name)
    if stem == base:
        return name
    rest = stem[len(base):]
    parts = re.findall(r" \(([^()]*)\)", rest)
    if "".join(f" ({p})" for p in parts) == rest:
        short = " ".join(parts)
        if song.parts(short + ext):
            return short + ext
    return name


def loose(container):
    """{song: [its file names]} of the songs loose in this folder (the old layout), and the other
    names in it. A song is there if some audio file is named just like it."""
    try:
        names = sorted(n for n in os.listdir(container) if (Path(container) / n).is_file())
    except OSError:
        return {}, []
    bases = {os.path.splitext(n)[0] for n in names
             if os.path.splitext(n)[1].lower() in AUDIO_EXTS and old_base(n) == os.path.splitext(n)[0]
             and not OLD.search(os.path.splitext(n)[0])}
    groups = {b: [] for b in bases}
    rest = []
    for n in names:
        ext = os.path.splitext(n)[1].lower()
        owner = None
        if ext in AUDIO_EXTS:
            owner = old_base(n)
        elif n.lower().endswith(PEAKS):
            owner = old_base(n[:-len(PEAKS)])
        else:
            owner = next((b for b in bases for c in COMPANIONS if n.lower() == (b + c).lower()), None)
        if owner in groups:
            groups[owner].append(n)
        else:
            rest.append(n)
    return groups, rest


def plain(base, names):
    """Whether a loose song is just its own files (added by hand or just downloaded): nothing made
    from it, no lyrics, no project."""
    return all(os.path.splitext(n)[0] == base for n in names)


def needed(container):
    """Whether this folder has songs in the old layout that tidy() has to move (songs that are
    just a file, added by hand, go to their folder on their own: see fold())."""
    container = Path(container)
    if any((container / f"{r}.txt").is_file() for r in RESULTS):
        return True
    groups, _ = loose(container)
    return any(not plain(b, names) for b, names in groups.items())


def fold(container, settle=SETTLING):
    """Songs that are just a file in a folder of songs (added by hand, or just downloaded) go to
    their own folder. Returns their main files in their new place."""
    container = Path(container)
    if needed(container) or busy(container):
        return []
    groups, _ = loose(container)
    now, done = time.time(), []
    for base, names in sorted(groups.items()):
        try:
            if settle and any(now - (container / n).stat().st_mtime < settle for n in names):
                continue
        except OSError:
            continue
        here = container / base
        if here.exists():
            continue
        here.mkdir()
        for n in names:
            os.rename(container / n, here / n)
        done.append(song.main_in(here))
    return done


def fold_one(path):
    """A song that is just a file, loose in a folder of songs (just downloaded): to its own folder,
    with its other formats (a .wav made from it). Returns its main file there."""
    path = Path(os.path.abspath(path))
    container, base = path.parent, path.stem
    if song.is_song(container):
        return song.main_in(container)
    here = container / base
    if here.exists() and not song.is_song(here):
        die(f"{here}: it's there already and isn't this song's folder.")
    here.mkdir(exist_ok=True)
    for n in os.listdir(container):
        if os.path.splitext(n)[0] == base and (container / n).is_file() and not (here / n).exists():
            os.rename(container / n, here / n)
    return song.main_in(here)


def read_results(container, command):
    """{file name: result} from the old <command>.txt of a folder."""
    lines = {}
    path = Path(container) / f"{command}.txt"
    if path.is_file():
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.startswith("#") and "\t" in line:
                name, text = line.split("\t", 1)
                lines[name] = text.strip()
    return lines


def tempo_line(bpm_text, click_text):
    """One tempo for the song from its old bpm.txt and click.txt lines. The practice click wins
    (it's where the beats fall, adjusted by ear): a tempo typed in bpm.txt only says the song's
    tempo was set by hand, so detecting again leaves it alone."""
    from . import align, results

    click = align.parse(click_text)
    if click:
        text = align.describe(click["bpm"], click["meter"], click["first"])
        return results.hand(text) if bpm_text and bpm_text.endswith(results.HAND) else text
    return bpm_text


def rewrite_project(text, names):
    """A REAPER project's text with the files it names moved to their new names."""
    pattern = re.compile(r'^(\s*(?:FILE|NAME)\s+)(["\'`])([^"\'`\r\n]*)(\2)', re.M)
    return pattern.sub(lambda m: m[1] + m[2] + names.get(m[3], m[3]) + m[4], text)


def plan(container):
    """What tidy() would do: {"moves": [(old, new)], "writes": {path: text}, "removes": [path],
    "projects": [path after the move]} (paths relative to the folder). Exits if it can't."""
    container = Path(container)
    groups, _ = loose(container)
    keys, bpms, clicks = (read_results(container, r) for r in RESULTS)
    # REAPER keeps its waveform caches next to each file, or in a "peaks" folder next to them.
    try:
        cached = set(os.listdir(container / "peaks")) if (container / "peaks").is_dir() else set()
    except OSError:
        cached = set()
    moves, writes, projects, clashes = [], {}, [], []
    for base, names in sorted(groups.items()):
        here = Path(base)
        if (container / here).exists():
            clashes.append(base + "/")
            continue
        own = sorted((n for n in names if os.path.splitext(n)[0] == base),
                     key=lambda n: MAIN_FORMATS.index(os.path.splitext(n)[1].lower())
                     if os.path.splitext(n)[1].lower() in MAIN_FORMATS else len(MAIN_FORMATS))
        renamed = {}
        for n in names:
            if n.lower().endswith(PEAKS) and n[:-len(PEAKS)] in names:
                continue
            target = next((v if v else n for c, v in COMPANIONS.items() if n.lower() == (base + c).lower()), None) \
                or new_name(n, base)
            renamed[n] = target
            if n + PEAKS in names:
                renamed[n + PEAKS] = target + PEAKS
        for n in names:  # peaks of a file that's gone
            renamed.setdefault(n, n)
        if len(set(t.lower() for t in renamed.values())) != len(renamed):
            clashes.append(base + "/ (two files would get the same name)")
            continue
        moves += [(n, str(here / t)) for n, t in renamed.items()]
        moves += [(f"peaks/{n}{PEAKS}", str(here / "peaks" / f"{t}{PEAKS}")) for n, t in renamed.items()
                  if f"{n}{PEAKS}" in cached]
        projects += [str(here / t) for t in renamed.values() if t.lower().endswith((".rpp", ".rpp-bak"))]
        key = next((keys[n] for n in own if n in keys), None)
        tempo = next((t for n in own if (t := tempo_line(bpms.get(n), clicks.get(n)))), None)
        if key:
            writes[str(here / song.DATA["key"])] = key
        if tempo:
            writes[str(here / song.DATA["tempo"])] = tempo
    if clashes:
        die(f"Nothing moved in {container}: these are already there:\n" + "\n".join(f"  {c}" for c in clashes))
    removes = [f"{r}.txt" for r in RESULTS if (container / f"{r}.txt").is_file()]
    return {"moves": moves, "writes": writes, "removes": removes, "projects": projects,
            "names": {n: Path(t).name for n, t in moves}}


def tidy(container, quiet=False):
    """Move the songs of this folder to a folder each. Returns how many songs it moved."""
    container = Path(os.path.abspath(container))
    if not container.is_dir():
        die(f"{container}: no such folder.")
    todo = plan(container)
    if not todo["moves"] and not todo["removes"]:
        if not quiet:
            print(f"{container}: nothing to move.")
        return 0
    if todo["projects"]:
        from . import reaper
        if reaper.running():
            die("Close REAPER first: it has these songs' projects and would write them back where they were.")
    record = {"date": f"{datetime.datetime.now():%Y-%m-%d %H:%M}", "moves": [], "created": [],
              "removed": {}, "projects": {}}
    try:
        for old, new in todo["moves"]:
            (container / new).parent.mkdir(parents=True, exist_ok=True)
            os.rename(container / old, container / new)
            record["moves"].append([old, new])
        for rel in todo["projects"]:
            path = container / rel
            text = path.read_text(encoding="utf-8", errors="surrogateescape")
            changed = rewrite_project(text, todo["names"])
            if changed != text:
                with open(path, "w", encoding="utf-8", errors="surrogateescape", newline="") as f:
                    f.write(changed)
                record["projects"][rel] = text
        for rel, text in todo["writes"].items():
            (container / rel).write_text(text + "\n", encoding="utf-8")
            record["created"].append(rel)
        for rel in todo["removes"]:
            record["removed"][rel] = (container / rel).read_text(encoding="utf-8", errors="replace")
            (container / rel).unlink()
    except OSError as e:
        put_back(container, record)
        die(f"Nothing moved in {container}: {e}")
    try:
        (container / "peaks").rmdir()  # REAPER's caches all went with their songs
    except OSError:
        pass
    songs_moved = [m for m in record["moves"] if not m[0].startswith("peaks/")]
    if (container / RECORD).is_file():  # a second time (songs copied in the old way later): both undo
        try:
            before = json.loads((container / RECORD).read_text(encoding="utf-8"))
            record = {"date": before.get("date", record["date"]), "moves": before.get("moves", []) + record["moves"],
                      "created": before.get("created", []) + record["created"],
                      "removed": {**record["removed"], **before.get("removed", {})},
                      "projects": {**record["projects"], **before.get("projects", {})}}
        except (OSError, ValueError):
            pass
    (container / RECORD).write_text(json.dumps(record, indent=1, ensure_ascii=False), encoding="utf-8")
    songs = len({Path(new).parts[0] for _, new in songs_moved})
    if not quiet:
        print(f"{container}: {songs} song{'s' if songs != 1 else ''} in a folder each "
              f'("song-wizard tidy --undo" puts them back).')
    return songs


def put_back(container, record):
    """Undo what the record says was done, last first."""
    for rel, text in record.get("removed", {}).items():
        (container / rel).write_text(text, encoding="utf-8")
    for rel in record.get("created", []):
        (container / rel).unlink(missing_ok=True)
    for rel, text in record.get("projects", {}).items():
        with open(container / rel, "w", encoding="utf-8", errors="surrogateescape", newline="") as f:
            f.write(text)
    folders = set()
    for old, new in reversed(record.get("moves", [])):
        if (container / new).exists() and not (container / old).exists():
            (container / old).parent.mkdir(exist_ok=True)
            os.rename(container / new, container / old)
        folders.add(container / Path(new).parts[0] / "peaks")
        folders.add(container / Path(new).parts[0])
    for f in sorted(folders, key=lambda p: -len(p.parts)):
        try:
            f.rmdir()
        except OSError:
            pass  # something new in it (a stem made after): it stays


def undo(container):
    container = Path(os.path.abspath(container))
    path = container / RECORD
    if not path.is_file():
        die(f"{container}: song-wizard didn't move anything there (there's no {RECORD}).")
    record = json.loads(path.read_text(encoding="utf-8"))
    if record.get("projects"):
        from . import reaper
        if reaper.running():
            die("Close REAPER first.")
    put_back(container, record)
    path.unlink()
    print(f"{container}: put back as it was on {record.get('date')}. "
          "Anything made since in the songs' folders stayed there.")


def run(folders, undo_it=False):
    from . import ui
    from .paths import music_dir

    if not folders:
        root = music_dir()
        folders = [root, *ui.subfolders_of(root)]
        from . import archives
        folders += [f for place in archives.places() for f in [place, *ui.subfolders_of(place)]]
        folders = [f for f in dict.fromkeys(Path(f) for f in folders)
                   if (undo_it and (f / RECORD).is_file()) or (not undo_it and needed(f))]
        if not folders:
            print("Nothing to do: every song is in its folder." if not undo_it else "Nothing to put back.")
            return
    for f in folders:
        undo(f) if undo_it else tidy(f)
