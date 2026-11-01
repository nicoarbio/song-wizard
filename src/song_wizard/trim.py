"""Trim a song: cut its start and/or end (a video's intro or credits), or add silence before or
after it. Done to the song and everything made from it at once, so they stay in step: its other
formats, stems, transposed versions and clicks with the same cut, and versions at another speed
with the cut scaled (at 80 %, 10 s of the song are 12.5 s). The practice click (click.txt) and the
lyrics' times move along. Takes recorded in REAPER are left alone: they line up with the REAPER
project, not with the song (whose project then needs remaking).

Cuts are exact to the sample, so the song and its stems keep lining up; compressed files are
encoded again at a high quality (cutting them without it rounds to ~20 ms). Everything is written
first next to the originals; only if every file worked are they swapped in, and the old ones go
to the trash."""

import json
import os
import re
import subprocess
import sys

from . import align, lyrics, reaper, results, system
from .audio import AUDIO_EXTS, GENERATED, base_of, die, require_ffmpeg
from .click import parse_duration
from .rename import group

MAX_PAD = 60
SPEED = re.compile(r"^ \((\d+(?:\.\d+)?)%(?:, [+-]\d+(?:\.\d+)?)?\)$")
TAKE = re.compile(r"^ \(record [^)]*\)(-\d+)?$")
# How each format is written again: the same format, at a quality where the second encoding
# doesn't show. WAV and AIFF keep their sample format (32-bit float stems stay float).
ENCODE = {
    ".opus": ["-c:a", "libopus", "-b:a", "256k", "-f", "opus"],
    ".webm": ["-c:a", "libopus", "-b:a", "256k", "-f", "webm"],
    ".mkv": ["-c:a", "libopus", "-b:a", "256k", "-f", "matroska"],
    ".ogg": ["-c:a", "libvorbis", "-q:a", "8", "-f", "ogg"],
    ".mp3": ["-c:a", "libmp3lame", "-q:a", "0", "-f", "mp3"],
    ".m4a": ["-c:a", "aac", "-b:a", "256k", "-f", "ipod"],
    ".mp4": ["-c:a", "aac", "-b:a", "256k", "-f", "mp4"],
    ".aac": ["-c:a", "aac", "-b:a", "256k", "-f", "adts"],
    ".flac": ["-c:a", "flac", "-f", "flac"],
    ".wav": ["-f", "wav"],
    ".aif": ["-f", "aiff"],
    ".aiff": ["-f", "aiff"],
}
NEW, OLD = ".trim-new", ".trim-old"


def suffixes(name):
    """'Title (drums) (80%).wav' -> [' (drums)', ' (80%)']: what was added to the song's name."""
    stem = os.path.splitext(name)[0]
    found = []
    while (match := GENERATED.search(stem)) and match.start() > 0:
        found.insert(0, stem[match.start():])
        stem = stem[:match.start()]
    return found


def scale(name):
    """How much longer this file's timeline is than the song's (2.0 at 50 % speed), or None for
    a file that isn't on the song's timeline (a take recorded in REAPER)."""
    factor = 1.0
    for s in suffixes(name):
        if TAKE.match(s):
            return None
        if m := SPEED.match(s):
            factor *= 100 / float(m[1])
    return factor


def probe(path):
    """(sample rate, codec name, duration in seconds) of the first audio stream."""
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a:0",
                          "-show_entries", "stream=sample_rate,codec_name:format=duration",
                          "-of", "json", str(path)], capture_output=True, text=True)
    try:
        info = json.loads(out.stdout)
        stream = info["streams"][0]
        return int(stream["sample_rate"]), stream["codec_name"], float(info["format"]["duration"])
    except (ValueError, KeyError, IndexError):
        die(f"{path}: could not read it as audio")


def plan(song, start=0.0, end=None, pad_start=0.0, pad_end=0.0):
    """What would be done: (folder, base, song's length, [(file name, factor)], [takes left
    alone], the end). Exits explaining why not if the cut doesn't make sense."""
    song = os.path.abspath(song)
    if not os.path.isfile(song):
        die(f"{song}: not found")
    folder, base = os.path.dirname(song), base_of(os.path.basename(song))
    length = probe(reaper.preferred(song))[2]
    end = length if end is None else end
    if not 0 <= start < end:
        die(f"The start ({start:.2f} s) has to come before the end ({end:.2f} s).")
    if end > length + 0.05:
        die(f"The song is {length:.2f} s long: the end can't be at {end:.2f} s.")
    if not (0 <= pad_start <= MAX_PAD and 0 <= pad_end <= MAX_PAD):
        die(f"Silence goes from 0 to {MAX_PAD} seconds.")
    if start == 0 and end >= length - 0.0005 and not pad_start and not pad_end:
        die("Nothing to do: no cut and no silence.")
    files, takes = [], []
    for name in group(folder, base):
        ext = os.path.splitext(name)[1].lower()
        if ext not in AUDIO_EXTS:
            continue  # lyrics, the REAPER project...
        factor = scale(name)
        if factor is None:
            takes.append(name)
        elif ext not in ENCODE:
            die(f"{name}: can't write {ext} files again")
        else:
            files.append((name, factor))
    return folder, base, length, files, takes, min(end, length)


def ffmpeg_args(source, target, start, end, length, pad_start, pad_end, factor):
    """The ffmpeg command that writes the trimmed file (in its own timeline: times x factor)."""
    sr, codec, duration = probe(source)
    a = round(start * factor * sr)
    # Not cutting the end: up to the file's own end (a stem can be a few samples longer).
    b = round(end * factor * sr) if end < length - 0.0005 else None
    filters = [f"atrim=start_sample={a}" + (f":end_sample={b}" if b is not None else ""), "asetpts=N/SR/TB"]
    if pad_start:
        filters.append(f"adelay=delays={round(pad_start * factor * sr)}S:all=1")
    if pad_end:
        filters.append(f"apad=pad_len={round(pad_end * factor * sr)}")
    ext = os.path.splitext(source)[1].lower()
    encode = ENCODE[ext]
    if ext in (".wav", ".aif", ".aiff"):
        encode = ["-c:a", codec, *encode]
    # The tags go along: a download's link among them, which deleting the song needs.
    return ["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", str(source), "-map", "0:a:0",
            "-map_metadata", "0", "-map_metadata:s:a:0", "0:s:a:0", "-af", ",".join(filters), *encode, str(target)]


def shift_click(folder, names, start, pad_start, factors):
    """The practice click's first beat, moved by the cut (by whole beats if it was cut off)."""
    changed = []
    clicks = results.read(folder, "click")
    for name in names:
        click = align.parse(clicks.get(name))
        if not click:
            continue
        first = click["first"] + (pad_start - start) * factors[name]
        beat = 60 / click["bpm"]
        if first < 0:
            first += -(first // beat) * beat
        changed.append((os.path.join(folder, name), align.describe(click["bpm"], click["meter"], first)))
    if changed:
        results.save("click", changed)
    return len(changed)


def shift_lyrics(song, start, pad_start):
    """The lyrics' times, moved by the cut; lines that were cut off lose their time."""
    data = lyrics.load(song)
    if not data:
        return False
    delta = pad_start - start
    data["times"] = {k: round(v + delta, 2) for k, v in (data.get("times") or {}).items() if v + delta >= 0}
    if data.get("synced"):
        data["synced"] = [[round(t + delta, 2), line] for t, line in data["synced"] if t + delta >= 0]
    lyrics.save(song, data)
    return True


def run(song, start=None, end=None, pad_start=0.0, pad_end=0.0, yes=False):
    require_ffmpeg()
    song = system.local_path(str(song))
    start = parse_duration(str(start)) if start not in (None, "") else 0.0
    end = parse_duration(str(end)) if end not in (None, "") else None
    folder, base, length, files, takes, end = plan(song, start, end, pad_start, pad_end)
    kept = end - start
    print(f"{base}: {length:.2f} s → keeps {start:.2f}–{end:.2f} s ({kept:.2f} s)"
          + (f", {pad_start:g} s of silence before" if pad_start else "")
          + (f", {pad_end:g} s of silence after" if pad_end else "")
          + f" = {kept + pad_start + pad_end:.2f} s")
    print(f"These {len(files)} files are trimmed (the old ones go to the trash):")
    for name, factor in files:
        print(f"  {name}" + (f"  (at {100 / factor:g} % speed: times x{factor:g})" if factor != 1 else ""))
    for name in takes:
        print(f"  {name}  (a REAPER take: left as it is)")
    if not yes:
        if not sys.stdin.isatty():
            die("Not trimming without confirmation: add --yes.")
        if input("Trim them? [y/N] ").strip().lower() not in ("y", "yes", "s", "si", "sí"):
            print("Nothing changed.")
            return
    # 1. Every new file next to its original; nothing is replaced unless all of them work.
    made = []
    try:
        for name, factor in files:
            source, target = os.path.join(folder, name), os.path.join(folder, name + NEW)
            done = subprocess.run(ffmpeg_args(source, target, start, end, length, pad_start, pad_end, factor),
                                  capture_output=True, text=True)
            made.append(target)
            if done.returncode != 0:
                die(f"Nothing changed: {name} couldn't be written: {done.stderr.strip()[-300:]}")
            print(f"  trimmed {name}", flush=True)
    except BaseException:
        for t in made:
            if os.path.exists(t):
                os.remove(t)
        raise
    # 2. Swap them in: the old ones aside first, so a failure can put everything back.
    swapped = []
    try:
        for name, _ in files:
            path = os.path.join(folder, name)
            os.replace(path, path + OLD)
            swapped.append(path)
            os.replace(path + NEW, path)
    except OSError as e:
        for path in swapped:
            if os.path.exists(path + OLD):
                os.replace(path + OLD, path)
        for t in made:
            if os.path.exists(t):
                os.remove(t)
        die(f"Nothing changed: {e}")
    # 3. The old ones to the trash (if that fails, they stay next to the new ones as ".trim-old").
    olds = [p + OLD for p in swapped]
    try:
        system.trash(olds)
    except system.TrashError as e:
        print(f"  The trimmed files are in place, but the old ones couldn't go to the trash ({e}): "
              f"they're next to them, ending in {OLD}; delete them when you like.")
    factors = dict(files)
    if n := shift_click(folder, list(factors), start, pad_start, factors):
        print(f"  moved the practice click's first beat ({n} file{'s' if n != 1 else ''})")
    if shift_lyrics(os.path.join(folder, files[0][0]), start, pad_start):
        print("  moved the lyrics' times")
    if reaper.existing(os.path.join(folder, files[0][0])):
        print("  the REAPER project is out of step now: remake it (song-wizard reaper --redo, or "
              "más › Rehacer proyecto de Reaper)")
    if takes:
        print(f"  {len(takes)} REAPER take{'s' if len(takes) != 1 else ''} left as {'they were' if len(takes) != 1 else 'it was'}")
    print(f"Trimmed {len(files)} file{'s' if len(files) != 1 else ''}.")
