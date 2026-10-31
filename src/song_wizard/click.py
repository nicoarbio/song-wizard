"""Steady click track: a given tempo, meter and length. Nothing is detected, so it's exact."""

import math
import os
import re
import subprocess

import numpy as np
import soundfile as sf

from .audio import die

SR = 44100
CLICK_SECONDS = 0.03
# (frequency, gain) for the first beat of the bar, the other beats and subdivisions.
ACCENT, BEAT, SUB = (1500, 0.7), (1000, 0.45), (800, 0.25)


def parse_meter(meter):
    match = re.fullmatch(r"\s*(\d+)\s*/\s*(\d+)\s*", meter)
    if not match or not 1 <= int(match.group(1)) <= 32:
        die(f'Invalid meter "{meter}": use something like 4/4, 3/4, 6/8 or 7/8.')
    return int(match.group(1)), int(match.group(2))


def parse_duration(text):
    """'4:30', '1:02:00' or '270' (seconds) -> seconds."""
    try:
        parts = [float(p) for p in text.split(":")]
    except ValueError:
        parts = []
    if not 1 <= len(parts) <= 3 or any(p < 0 for p in parts):
        die(f'Invalid duration "{text}": use minutes:seconds (4:30) or seconds (270).')
    return sum(p * 60 ** i for i, p in enumerate(reversed(parts)))


def file_duration(path):
    if not os.path.isfile(path):
        die(f"{path}: not found")
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "default=nw=1:nk=1", path], capture_output=True, text=True)
    try:
        return float(out.stdout.strip())
    except ValueError:
        die(f"{path}: could not read its duration")


def tone(freq, gain):
    t = np.arange(int(CLICK_SECONDS * SR)) / SR
    return (gain * np.sin(2 * np.pi * freq * t) * np.exp(-t / 0.006)).astype(np.float32)


def run(bpm, meter="4/4", duration=None, bars=None, like=None, subdivide=1, output=None):
    if not 20 <= bpm <= 400:
        die("The tempo must be between 20 and 400 BPM.")
    if not 1 <= subdivide <= 8:
        die("--subdivide must be between 1 and 8.")
    per_bar, unit = parse_meter(meter)
    beat = 60 / bpm
    bar = beat * per_bar

    if bars is None:
        seconds = file_duration(like) if like else parse_duration(duration or "1:00")
        # Always whole bars, at least the requested length.
        bars = max(1, math.ceil(seconds / bar - 1e-9))
    elif bars < 1:
        die("--bars must be 1 or more.")

    total = bars * per_bar * subdivide
    track = np.zeros(round(bars * bar * SR) + int(CLICK_SECONDS * SR), dtype=np.float32)
    sounds = {"accent": tone(*ACCENT), "beat": tone(*BEAT), "sub": tone(*SUB)}
    for k in range(total):
        # Each click's position comes from its index, so there's no drift however long it is.
        i = round(k * beat / subdivide * SR)
        kind = "sub" if k % subdivide else ("accent" if (k // subdivide) % per_bar == 0 else "beat")
        s = sounds[kind]
        track[i:i + len(s)] += s

    name = f"Click {bpm:g} BPM {per_bar}-{unit}" + (f" x{subdivide}" if subdivide > 1 else "") + ".wav"
    out = name if output is None else (os.path.join(output, name) if os.path.isdir(output) else output)
    sf.write(out, track, SR, subtype="PCM_16")
    minutes, secs = divmod(bars * bar, 60)
    print(f"  {bpm:g} BPM  {meter}  {bars} bars ({int(minutes)}:{secs:05.2f})"
          + (f"  subdivided by {subdivide}" if subdivide > 1 else "") + f"  {out}")
