"""Tempo detection with Essentia, plus how steady the tempo is across the song."""

import os
import subprocess

import numpy as np

from . import results
from .audio import expand, load

# Tempo is measured over sliding windows of this many beats.
WINDOW = 8
# Spread between the 10th and 90th percentile of the windowed tempo, relative to the tempo.
STEADY = 0.02
UNSTABLE = 0.10
# RhythmExtractor2013's confidence goes from 0 to 5.32; below 1 Essentia calls it very low.
LOW_CONFIDENCE = 1.0
MIN_BPM, MAX_BPM = 50, 220


def analyze(audio):
    """Mono 44.1 kHz audio -> (bpm, beat times in seconds, low and high tempo, confidence)."""
    import essentia
    essentia.log.infoActive = False
    essentia.log.warningActive = False
    import essentia.standard as es

    bpm, beats, confidence, _, _ = es.RhythmExtractor2013(method="multifeature")(audio)
    beats = np.asarray(beats, dtype=np.float64)
    local = 60 / np.convolve(np.diff(beats), np.ones(WINDOW) / WINDOW, mode="valid")
    low, high = np.percentile(local, [10, 90]) if len(local) else (bpm, bpm)
    return bpm, beats, low, high, confidence


def describe(bpm, low, high, confidence):
    """'steady', 'varies ...' or 'uncertain ...', and whether the result can be trusted."""
    spread = (high - low) / bpm
    if confidence < LOW_CONFIDENCE or spread > UNSTABLE:
        # Detectors usually miss by a factor of two; only suggest tempos a song could have.
        others = [f"{t:.1f}" for t in (bpm / 2, bpm * 2) if MIN_BPM <= t <= MAX_BPM]
        return "uncertain, check by ear" + (f" (could be {' or '.join(others)})" if others else ""), False
    if spread > STEADY:
        return f"varies {low:.0f}-{high:.0f}, probably played without a click", True
    return "steady", True


def run(paths):
    found = []
    for f in expand(paths, skip_generated=True):
        try:
            audio, _ = load(f, sr=44100, mono=True)
        except subprocess.CalledProcessError:
            print(f"  {'??':>6}      {os.path.basename(f)}  (could not read)")
            continue
        bpm, _, low, high, confidence = analyze(audio[0])
        note, _ = describe(bpm, low, high, confidence)
        print(f"  {bpm:6.1f} BPM  {os.path.basename(f)}  {note}")
        found.append((f, f"{bpm:.1f} BPM  {note}"))
    for out in results.save("bpm", found):
        print(f"Saved to {out}")
