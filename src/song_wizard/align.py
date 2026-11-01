"""Where a song's beats fall, for a click that plays along with it: the exact tempo, the meter
and the time of the first beat. Detected from the audio, or set by hand; saved in click.txt next
to the songs (one line per song, like key.txt and bpm.txt), which the practice player reads."""

import os
import re
import subprocess

import numpy as np

from . import results
from .audio import die, expand, load
from .click import parse_meter

# "120.25 BPM 4/4, first beat 0.512 s"
FORMAT = re.compile(r"(?P<bpm>\d+(?:\.\d+)?) BPM (?P<meter>\d+/\d+), first beat (?P<first>-?\d+(?:\.\d+)?) s")
SR = 44100
# Essentia's beats come 10-30 ms after the attack; each is moved to the nearest onset this close.
ONSET_WINDOW = 0.06
# OnsetRate reports an onset at the start of its analysis frame: one hop (512 samples) early.
ONSET_LAG = 512 / SR
PAD = 0.1


def describe(bpm, meter, first):
    return f"{bpm:.2f} BPM {meter}, first beat {first:.3f} s"


def parse(text):
    """click.txt result -> {"bpm", "meter", "first"}, or None."""
    match = FORMAT.search(text or "")
    if not match:
        return None
    return {"bpm": float(match["bpm"]), "meter": match["meter"], "first": float(match["first"])}


def detect(audio):
    """Mono 44.1 kHz audio -> (bpm, first beat in seconds, steady?), or None without a beat.

    Essentia's beats come 10-30 ms after the attack, and at the start of a song it also places
    beats in the silence before the music. So only beats with a real attack (an onset) close by
    count, at the onset's time; a straight line through them gives the beat length (the tempo,
    with decimals) and where the grid falls. The first beat is the first grid point where there
    is already sound."""
    import essentia.standard as es

    from .bpm import analyze, describe as describe_tempo

    # Onsets in the first ~50 ms of a file come out wrong: give the analysis some silence first.
    audio = np.concatenate([np.zeros(int(PAD * SR), dtype=np.float32), audio])
    found, beats, low, high, confidence = analyze(audio)
    onsets, _ = es.OnsetRate()(audio)
    if len(beats) < 8 or len(onsets) < 8:
        return None
    onsets = onsets + ONSET_LAG
    hits = []
    for b in beats:
        i = np.searchsorted(onsets, b)
        candidates = onsets[max(0, i - 1):i + 1]
        nearest = candidates[np.argmin(np.abs(candidates - b))]
        if abs(nearest - b) <= ONSET_WINDOW:
            hits.append(nearest)
    hits = np.unique(hits)
    if len(hits) < 8:
        return None
    period = 60 / found
    index = np.round((hits - hits[0]) / period)
    slope, intercept = np.polyfit(index, hits, 1)
    # Beat trackers sometimes lock onto the off-beats (a hi-hat on every eighth): of the grid and
    # the grid half a beat later, keep the one where the music is louder (kick and snare).
    if loudness(audio, intercept + slope / 2, slope) > 1.2 * loudness(audio, intercept, slope):
        intercept += slope / 2
    # The first grid point at or after the first sound (a little earlier counts: onsets jitter).
    k = np.ceil((onsets[0] - ONSET_WINDOW / 2 - intercept) / slope)
    _, trusted = describe_tempo(found, low, high, confidence)
    return 60 / slope, float(intercept + k * slope) - PAD, trusted and (high - low) / found <= 0.02


def loudness(audio, start, period, window=0.05):
    """Mean RMS of the audio in the first 50 ms of each grid point."""
    n = int(window * SR)
    points = start + period * np.arange(np.ceil(-start / period), (len(audio) / SR - start) / period)
    levels = [np.sqrt(np.mean(audio[int(t * SR):int(t * SR) + n] ** 2)) for t in points if t >= 0]
    return float(np.mean(levels)) if levels else 0.0


def run(paths, bpm=None, meter="4/4", first=None):
    per_bar, unit = parse_meter(meter)
    meter = f"{per_bar}/{unit}"
    if bpm is not None and not 20 <= bpm <= 400:
        die("The tempo must be between 20 and 400 BPM.")
    found = []
    for f in expand(paths, skip_generated=True):
        name = os.path.basename(f)
        song_bpm, song_first, note = bpm, first, ""
        if song_bpm is None or song_first is None:
            try:
                audio, _ = load(f, sr=44100, mono=True)
            except subprocess.CalledProcessError:
                print(f"  ??  {name}  (could not read)")
                continue
            detected = detect(audio[0])
            if detected is None:
                print(f"  ??  {name}  (no steady beat found; set it with --bpm and --first)")
                continue
            d_bpm, d_first, steady = detected
            song_bpm = d_bpm if song_bpm is None else song_bpm
            song_first = d_first if song_first is None else song_first
            if not steady:
                note = "  the tempo varies: a steady click will drift from the recording"
        text = describe(song_bpm, meter, song_first)
        print(f"  {text}  {name}{note}")
        found.append((f, text))
    for out in results.save("click", found):
        print(f"Saved to {out}")
