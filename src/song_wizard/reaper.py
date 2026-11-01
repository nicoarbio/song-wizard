"""A REAPER project for a song: "<song>.rpp" next to it, with a track per stem (or the song
itself), the project's tempo and meter from the practice click (click.txt) and the audio placed so
the song's first beat falls on a bar line, REAPER's own click on a track of its own, and a track
armed to record. If the project exists it's just opened, never rewritten: it may have been edited
in REAPER.

Takes recorded in REAPER are named "<song> (record 2026-11-01 19-05-12).wav", so they're grouped
with their song. REAPER only has that setting globally (Preferences > Recording > recorded
filenames), so it's set in reaper.ini when REAPER is closed, with a copy of the file kept first."""

import datetime
import json
import math
import os
import re
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

from . import align, log, results, system
from .audio import AUDIO_EXTS, MAIN_FORMATS, base_of, die
from .paths import DATA_DIR, is_wsl

SUFFIX = ".rpp"
BACKUP = "reaper.ini.before-song-wizard"
# What song-wizard changed in REAPER's settings, to say so and to put it back.
STATE = DATA_DIR / "reaper.json"
# Recorded takes: "$project" is the project's file name, which is the song's.
TAKES = "$project (record $year-$month-$day $hour-$minute-$second)"
STEM_NAMES = {"vocals": "Voz", "drums": "Batería", "bass": "Bajo", "guitar": "Guitarra", "piano": "Piano", "other": "Otros",
              "kick": "Bombo", "snare": "Redoblante", "toms": "Toms", "hihat": "Hi-hat", "ride": "Ride", "crash": "Crash",
              "drums rest": "Resto de la batería"}
KIT = ["kick", "snare", "toms", "hihat", "ride", "crash", "drums rest"]
FULL_SET = ["vocals", "drums", "bass", "guitar", "other"]


def path_for(song):
    song = Path(song)
    return song.parent / f"{base_of(song.name)}{SUFFIX}"


def existing(song):
    """The song's project if there is one ("<song>.rpp", any case), else None."""
    song = Path(song)
    wanted = f"{base_of(song.name)}{SUFFIX}".lower()
    try:
        return next((song.parent / n for n in os.listdir(song.parent)
                     if n.lower() == wanted and (song.parent / n).is_file()), None)
    except OSError:
        return None


# --- which files go in -----------------------------------------------------------------------

def tracks_for(song):
    """[(track name, file name, muted)]: the best set of stems playing (the same the practice
    player starts with: every stem, or an instrument with the rest, or the song itself), and the
    other stems and the original song muted, so they're there to switch to."""
    song = Path(song)
    base = base_of(song.name)
    stem = re.compile(rf"^{re.escape(base)} \(((?:no )?(?:vocals|drums|bass|guitar|piano)|other|kick|snare|toms|hihat|ride|crash|drums rest)\)\.wav$", re.I)
    found = {}
    for n in sorted(os.listdir(song.parent)):
        if (m := stem.match(n)) and (song.parent / n).is_file():
            found[m[1].lower()] = n
    name = lambda k: f"Sin {STEM_NAMES[k[3:]].lower()}" if k.startswith("no ") else STEM_NAMES[k]
    if all(k in found for k in FULL_SET):
        playing = FULL_SET
    else:
        pair = next((k for k in ("vocals", "drums", "bass", "guitar", "piano") if k in found and f"no {k}" in found), None)
        playing = [pair, f"no {pair}"] if pair else []
    order = [*FULL_SET, "piano", *(f"no {k}" for k in [*FULL_SET[:4], "piano"]), *KIT]
    tracks = [(name(k), found[k], False) for k in playing]
    tracks += [(name(k), found[k], True) for k in order if k in found and k not in playing]
    tracks.append(("Tema original", song.name, bool(playing)))
    return tracks


# --- timing ----------------------------------------------------------------------------------

def timing(song):
    """(bpm, beats per bar, beat unit, where the audio starts in the project, problem): problem is
    None, "unaligned" (a tempo, but not where the beats fall) or "no-tempo"."""
    song = Path(song)
    folder = str(song.parent)
    click = align.parse(results.read(folder, "click").get(song.name))
    if click:
        beats, unit = (int(x) for x in click["meter"].split("/"))
        bar = beats * 60 / click["bpm"]
        # The first bar line after the first beat... minus where it is in the file: the song's
        # first beat lands on that bar line, with at least a bar of click before it.
        start = (math.floor(click["first"] / bar) + 1) * bar - click["first"]
        return click["bpm"], beats, unit, start, None
    text = results.read(folder, "bpm").get(song.name)
    if text and (m := re.match(r"\s*(\d+(?:\.\d+)?)", text)):
        return float(m[1]), 4, 4, 0.0, "unaligned"
    return 120.0, 4, 4, 0.0, "no-tempo"


def duration(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "default=nw=1:nk=1", str(path)], capture_output=True, text=True)
    try:
        return float(out.stdout.strip())
    except ValueError:
        die(f"{path}: could not read its duration")


# --- the project file ------------------------------------------------------------------------

def guid():
    return "{" + str(uuid.uuid4()).upper() + "}"


def quoted(text):
    """A string as REAPER writes it: in double quotes, or in single quotes or backticks if it
    has double quotes (it has no escaping)."""
    for q in ('"', "'", "`"):
        if q not in text:
            return f"{q}{text}{q}"
    return '"' + text.replace('"', "'") + '"'


def track(name, item=None, muted=False, record=False):
    tid = guid()
    lines = [f"  <TRACK {tid}",
             f"    NAME {quoted(name)}",
             "    PEAKCOL 16576",
             "    BEAT -1",
             "    AUTOMODE 0",
             "    VOLPAN 1 0 -1 -1 1",
             f"    MUTESOLO {int(muted)} 0 0",
             "    IPHASE 0",
             "    ISBUS 0 0",
             "    SHOWINMIX 1 0.6667 0.5 1 0.5 0 0 0 0",
             "    SEL 0",
             # Armed to record from inputs 1/2 (stereo), with monitoring (hearing the input) off.
             "    REC 1 1024 0 0 0 0 0 0" if record else "    REC 0 0 1 0 0 0 0 0",
             "    VU 64",
             "    TRACKHEIGHT 0 0 0 0 0 0 0",
             "    INQ 0 0 0 0.5 100 0 0 100",
             "    NCHAN 2",
             "    FX 1",
             f"    TRACKID {tid}",
             "    PERF 0",
             "    MIDIOUT -1 -1",
             "    MAINSEND 1 0"]
    if item:
        lines += ["    " + l if l else l for l in item]
    lines.append("  >")
    return lines


def item(name, position, length, source):
    return ["<ITEM",
            f"  POSITION {position:.10f}",
            "  SNAPOFFS 0",
            f"  LENGTH {length:.10f}",
            "  LOOP 0",
            "  ALLTAKES 0",
            "  FADEIN 1 0 0 1 0 0 0",
            "  FADEOUT 1 0 0 1 0 0 0",
            "  MUTE 0 0",
            "  SEL 0",
            f"  IGUID {guid()}",
            f"  NAME {quoted(name)}",
            "  VOLPAN 1 0 1 -1",
            "  SOFFS 0",
            "  PLAYRATE 1 1 0 -1 0 0.0025",
            "  CHANMODE 0",
            f"  GUID {guid()}",
            *["  " + l for l in source],
            ">"]


# REAPER's source type for each format: with the wrong one, the item is there but silent. (Each
# checked by rendering a project with REAPER 7.84.)
SOURCES = {".wav": "WAVE", ".aif": "WAVE", ".aiff": "WAVE", ".flac": "FLAC", ".mp3": "MP3", ".opus": "OPUS",
           ".ogg": "VORBIS", ".m4a": "VIDEO", ".mp4": "VIDEO", ".aac": "VIDEO", ".webm": "VIDEO", ".mkv": "VIDEO"}


def source(file):
    kind = SOURCES.get(os.path.splitext(file)[1].lower(), "VIDEO")
    return [f"<SOURCE {kind}", f"  FILE {quoted(file)}", ">"]


def click_source(bpm, beats):
    # REAPER's click follows the project's tempo map: fix the tempo in REAPER and it follows.
    return ["<SOURCE CLICK",
            "  AUTO 1 0",
            f"  BPM {bpm:.10g}",
            f"  BPI {beats} 4",
            "  VOL 0.5 0.25",
            "  BEATLEN 4",
            "  FREQ 1760 880 1",
            '  SAMPLES "" "" "" ""',
            "  SPLIGNORE 0 0",
            '  SPLDEF 2 660 "" 0 ""',
            '  SPLDEF 3 440 "" 0 ""',
            "  PATTERN 0 169",
            f"  PATTERNSTR A{'B' * (beats - 1)}",
            "  MULT 1",
            ">"]


def build(song):
    """The project's text for the song, and the timing problem (see timing) or None."""
    song = Path(song)
    bpm, beats, unit, start, note = timing(song)
    tracks = tracks_for(song)
    length = duration(song)
    end = start + length
    lines = ['<REAPER_PROJECT 0.1 "7.0/song-wizard" 0 0',
             "  RIPPLE 0 0",
             "  AUTOXFADE 129",
             "  PANLAW 1",
             "  PROJOFFS 0 0 0",
             "  MAXPROJLEN 0 0",
             "  GRID 3199 8 1 8 1 0 0 0",
             "  TIMEMODE 1 5 -1 30 0 0 -1 0",
             "  PANMODE 3",
             "  CURSOR 0",
             "  ZOOM 3 0 0",
             "  VZOOMEX 6 0",
             "  USE_REC_CFG 0",
             "  RECMODE 1",
             "  LOOP 0",
             # Takes next to the project (and the song), where the library groups them with it.
             '  RECORD_PATH "" ""',
             "  <RECORD_CFG",
             "    ZXZhdxgAAQ==",
             "  >",
             "  SAMPLERATE 44100 0 0",
             "  LOCK 1",
             "  GLOBAL_AUTO -1",
             f"  TEMPO {bpm:.10g} {beats} {unit} 0",
             "  PLAYRATE 1 0 0.25 4",
             "  MASTERAUTOMODE 0",
             "  MASTER_NCH 2 2",
             "  MASTER_VOLUME 1 0 -1 -1 1",
             "  MASTER_PANMODE 3",
             "  MASTER_FX 1",
             "  MASTER_SEL 0"]
    for name, file, muted in tracks:
        lines += track(name, item(file, start, duration(song.parent / file), source(file)), muted=muted)
    lines += track("Click", item("Click", 0, end, click_source(bpm, beats)))
    lines += track("Grabación", record=True)
    lines.append(">")
    return "\n".join(lines) + "\n", note


def rename_inside(path, old, new):
    """After a rename: the files the project points to that started with the song's old name
    now start with the new one."""
    with open(path, encoding="utf-8", errors="surrogateescape", newline="") as f:  # REAPER writes \r\n
        text = f.read()
    pattern = re.compile(r'^(\s*(?:FILE|NAME)\s+)(["\'`])' + re.escape(old) + r'(?=[ .])', re.M)
    changed = pattern.sub(lambda m: m[1] + m[2] + new, text)
    if changed != text:
        with open(path, "w", encoding="utf-8", errors="surrogateescape", newline="") as f:
            f.write(changed)
    return changed != text


# --- REAPER on this computer -----------------------------------------------------------------

def installed():
    """Whether REAPER seems to be installed (so a project can be opened with it)."""
    if is_wsl():
        for root in ("/mnt/c/Program Files/REAPER (x64)", "/mnt/c/Program Files/REAPER",
                     "/mnt/c/Program Files (x86)/REAPER"):
            if os.path.isfile(f"{root}/reaper.exe"):
                return True
        if shutil.which("cmd.exe"):
            out = subprocess.run(["cmd.exe", "/c", "assoc", ".rpp"], capture_output=True,
                                 cwd="/mnt/c" if os.path.isdir("/mnt/c") else None)
            return b"=" in out.stdout
        return False
    if sys.platform == "darwin":
        return any(os.path.isdir(p) for p in ("/Applications/REAPER.app",
                                              os.path.expanduser("~/Applications/REAPER.app")))
    return bool(shutil.which("reaper")) or os.path.isfile(os.path.expanduser("~/opt/REAPER/reaper"))


def ini_path():
    if is_wsl():
        if not shutil.which("cmd.exe"):
            return None
        out = subprocess.run(["cmd.exe", "/c", "echo", "%APPDATA%"], capture_output=True,
                             cwd="/mnt/c" if os.path.isdir("/mnt/c") else None).stdout.decode("utf-8", "replace").strip()
        return Path(system.local_path(out)) / "REAPER" / "reaper.ini" if ":" in out else None
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "REAPER" / "reaper.ini"
    return Path.home() / ".config" / "REAPER" / "reaper.ini"


def running():
    if is_wsl():
        if not shutil.which("tasklist.exe"):
            return False
        out = subprocess.run(["tasklist.exe", "/FI", "IMAGENAME eq reaper.exe", "/NH"], capture_output=True,
                             cwd="/mnt/c" if os.path.isdir("/mnt/c") else None).stdout.decode("utf-8", "replace")
        return "reaper.exe" in out.lower()
    out = subprocess.run(["pgrep", "-x", "REAPER" if sys.platform == "darwin" else "reaper"], capture_output=True)
    return out.returncode == 0


KEY = "recfile_wildcards"


def read_ini(ini):
    with open(ini, encoding="utf-8", errors="surrogateescape", newline="") as f:  # keep its \r\n
        return f.read()


def current_value(text):
    """The recorded filenames setting in reaper.ini's text, or None if it's REAPER's default."""
    line = re.search(rf"^{KEY}=(.*?)\r?$", text, re.M)
    return line[1] if line else None


def write_value(ini, value):
    """Set the recorded filenames setting (None: back to REAPER's default, without the line),
    leaving the rest of the file as it is."""
    text = read_ini(ini)
    newline = "\r\n" if "\r\n" in text else "\n"
    line = re.search(rf"^{KEY}=.*?(\r?\n|$)", text, re.M)
    if value is None:
        text = text[:line.start()] + text[line.end():] if line else text
    elif line:
        text = text[:line.start()] + f"{KEY}={value}" + line[1] + text[line.end():]
    elif re.search(r"^\[reaper\]\r?\n", text, re.M):
        text = re.sub(r"^\[reaper\]\r?\n", lambda m: m[0] + f"{KEY}={value}" + newline, text, count=1, flags=re.M)
    else:
        text = f"[reaper]{newline}{KEY}={value}{newline}" + text
    with open(ini, "w", encoding="utf-8", errors="surrogateescape", newline="") as f:
        f.write(text)


def load_state():
    """What song-wizard changed in REAPER's settings: {"ini", "before", "changed", "declined",
    "restored"}, or {} if nothing."""
    try:
        return json.loads(STATE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_state(state):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, indent=1), encoding="utf-8")


def take_names(ini=None):
    """Make REAPER name recorded takes after the project (the song). Returns None if it already
    does, if REAPER never ran here (there's no settings file yet) or if the user put the setting
    back (restore) and so doesn't want it changed; "running" if REAPER is open (it rewrites
    reaper.ini on exit, so it can't be changed then); or "set"."""
    ini = Path(ini) if ini else ini_path()
    if not ini or not ini.is_file() or load_state().get("declined"):
        return None
    before = current_value(read_ini(ini))
    if before == TAKES:
        return None
    if running():
        return "running"
    backup = ini.with_name(BACKUP)
    if not backup.exists():
        shutil.copy2(ini, backup)
    write_value(ini, TAKES)
    save_state({"ini": str(ini), "before": before, "changed": f"{datetime.datetime.now():%Y-%m-%d %H:%M}",
                "declined": False})
    log.info("reaper: set %s in %s (it was %r)", KEY, ini, before)
    return "set"


def setting():
    """The state of the takes setting, for showing it: {"ini", "backup", "current", "ours" (takes
    go with their song), "changed" (when song-wizard changed it, or None), "before" (the value it
    had then; None is REAPER's default), "declined" (put back by the user), "running"}."""
    ini = ini_path()
    state = load_state()
    current = current_value(read_ini(ini)) if ini and ini.is_file() else None
    backup = ini.with_name(BACKUP) if ini else None
    changed, before = state.get("changed"), state.get("before")
    if not changed and current == TAKES and backup and backup.is_file():
        # Changed before song-wizard kept a record of it: the copy it made then says how it was.
        changed = f"{datetime.datetime.fromtimestamp(backup.stat().st_mtime):%Y-%m-%d %H:%M}"
        before = current_value(read_ini(backup))
    return {"ini": system.shown_path(ini) if ini else None, "exists": bool(ini and ini.is_file()),
            "backup": system.shown_path(backup) if backup and backup.is_file() else None,
            "current": current, "ours": current == TAKES, "takes": TAKES,
            "changed": changed if current == TAKES else None, "before": before,
            "declined": bool(state.get("declined")), "restored": state.get("restored"), "running": running()}


def restore():
    """Put the setting back as it was before song-wizard changed it, and don't change it again
    (until apply). Returns "restored", "running" or "not-changed"."""
    now = setting()
    if not now["changed"]:
        return "not-changed"
    if now["running"]:
        return "running"
    write_value(ini_path(), now["before"])
    save_state({**load_state(), "before": now["before"], "declined": True,
                "restored": f"{datetime.datetime.now():%Y-%m-%d %H:%M}"})
    log.info("reaper: put %s back to %r", KEY, now["before"])
    return "restored"


def apply():
    """Let song-wizard set it again (after a restore), and set it now. Returns take_names'."""
    state = load_state()
    if state.get("declined"):
        save_state({**state, "declined": False})
    return take_names()


def open_project(path):
    """Open it with REAPER (the program .rpp files open with). Returns whether it could."""
    if not installed():
        return False
    path = Path(path)
    if is_wsl() and shutil.which("explorer.exe"):
        system.launch(["explorer.exe", system.windows_path(path)])
    elif sys.platform == "darwin":
        system.launch(["open", "-a", "REAPER", str(path)])
    elif shutil.which("reaper"):
        system.launch(["reaper", str(path)])
    elif shutil.which("xdg-open"):
        system.launch(["xdg-open", str(path)])
    else:
        return False
    return True


# --- the command -----------------------------------------------------------------------------

def make(song, redo=False):
    """Create the song's project unless it exists (redo sends the old one to the trash first).
    Returns (project path, created?, {"timing": see timing, "takes": see take_names,
    "trashed": the old project went to the trash})."""
    song = Path(song)
    if not song.is_file():
        die(f"{song}: not found")
    if os.path.splitext(song.name)[1].lower() not in AUDIO_EXTS:
        die(f"{song.name}: not an audio file")
    song = preferred(song)
    project = existing(song)
    # Also for a project that exists: REAPER may have been open when it was made.
    info = {"timing": None, "takes": take_names() if installed() else None, "trashed": False}
    if project and not redo:
        return project, False, info
    if project:
        try:
            system.trash([str(project)])
        except system.TrashError as e:
            die(f"Stopped: {e}")
        info["trashed"] = True
    project = path_for(song)
    text, info["timing"] = build(song)
    project.write_text(text, encoding="utf-8")
    return project, True, info


def preferred(path):
    """Of the song's own files (not its stems or versions), the one the library shows."""
    path = Path(path)
    base = base_of(path.name)
    own = [n for n in os.listdir(path.parent)
           if os.path.splitext(n)[0] == base and os.path.splitext(n)[1].lower() in AUDIO_EXTS]
    if not own:
        die(f"{path.name}: its song isn't in this folder")
    rank = lambda n: (MAIN_FORMATS.index(os.path.splitext(n)[1].lower())
                      if os.path.splitext(n)[1].lower() in MAIN_FORMATS else len(MAIN_FORMATS))
    return path.parent / min(own, key=rank)


def notes(info):
    lines = []
    if info["trashed"]:
        lines.append("the project from before went to the trash")
    if info["timing"] == "unaligned":
        lines.append("tempo from bpm.txt, but the song isn't lined up with the bars: set the practice click "
                     "(song-wizard align, or practice → adjust the click) and --redo")
    elif info["timing"] == "no-tempo":
        lines.append("no tempo known for this song (run bpm or align first): the project is at 120 BPM")
    if info["takes"] == "set":
        lines += changed_message()
    elif info["takes"] == "running":
        lines.append("to have recorded takes go with their song, close REAPER and run this again (or set "
                     f'Options > Preferences > Recording > "Recorded filenames" to: {TAKES})')
    return lines


def shown(value):
    return "REAPER's default" if value is None else value


def changed_message():
    now = setting()
    return ["CHANGED A REAPER SETTING, for all your REAPER projects: Options > Preferences > Recording > "
            '"Recorded filenames"',
            f"    before: {shown(now['before'])}",
            f"    now:    {TAKES}",
            '    so takes are named "<song> (record <date> <time>).wav" and go with their song.',
            f"    in {now['ini']} (a copy from before: {now['backup']})",
            "    to put it back: song-wizard reaper --setting restore (or the Reaper box in the interface)"]


def run_setting(action):
    if action == "restore":
        done = restore()
        if done == "running":
            die("REAPER is open: close it first (it rewrites its settings when it closes).")
        if done == "not-changed":
            print("song-wizard hasn't changed REAPER's settings: nothing to put back.")
            return
        print(f"Put back REAPER's recorded filenames setting: {shown(setting()['before'])}. song-wizard won't change "
              "it again (song-wizard reaper --setting apply lets it); new takes won't go with their song.")
        return
    if action == "apply":
        done = apply()
        if done == "running":
            die("REAPER is open: close it first (it rewrites its settings when it closes).")
        if done == "set":
            print("\n".join(changed_message()))
            return
    now = setting()
    if not now["exists"]:
        print("REAPER hasn't run on this computer yet (no settings file): nothing changed.")
    elif now["ours"]:
        print(f'REAPER names recorded takes "{TAKES}", so they go with their song.')
        if now["changed"]:
            print(f"song-wizard changed it on {now['changed']}; before, it was: {shown(now['before'])}")
            print("To put it back: song-wizard reaper --setting restore")
    else:
        print(f"REAPER's recorded filenames: {shown(now['current'])}. Takes don't go with their song.")
        if now["declined"]:
            print(f"Put back on {now['restored']}; song-wizard won't change it again unless: song-wizard reaper --setting apply")
        else:
            print("song-wizard sets it when it makes or opens a project (with REAPER closed).")


def run(song, redo=False, yes=False, open_it=True):
    song = Path(system.local_path(str(song)))
    if redo and existing(song) and not yes:
        if not sys.stdin.isatty():
            die("Not replacing the project without confirmation: add --yes.")
        if input(f"{existing(song).name} goes to the trash (with whatever you changed in REAPER) and a new one "
                 "is made. Go on? [y/N] ").strip().lower() not in ("y", "yes", "s", "si", "sí"):
            print("Nothing changed.")
            return
    project, created, info = make(song, redo=redo)
    print(f"{'Created' if created else 'Already there'}: {system.shown_path(project)}")
    for line in notes(info):
        print(f"  {line}")
    if open_it:
        if open_project(project):
            print("Opening it in REAPER.")
        else:
            print("REAPER doesn't seem to be installed on this computer, so it wasn't opened.")
