"""Tempo detection with Essentia, plus how steady the tempo is across the song."""

import re
import subprocess

import numpy as np

from . import align, results, song
from .audio import die, load

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


def parse(text):
    """A tempo as typed ("120", "98.5", "120 BPM", "98,5") -> float, or None outside 20-400."""
    match = re.fullmatch(r"(\d+(?:[.,]\d+)?)\s*(?:bpm)?", (text or "").strip(), re.IGNORECASE)
    value = float(match[1].replace(",", ".")) if match else None
    return value if value and 20 <= value <= 400 else None


def set_by_hand(paths, text):
    value = parse(str(text))
    if value is None:
        die(f'"{text}" is not a tempo: a number of BPM between 20 and 400.')
    for f in song.expand(paths):
        result = with_tempo(f, value)
        print(f"  {value:6.1f} BPM  {f.name}")
        print(f"Saved to {results.save(f, 'tempo', result)}")


def with_tempo(path, value):
    """The song's tempo line at this BPM, set by hand. Where the beats fall stays (the first
    beat and the meter), so the practice click follows the new tempo."""
    found = align.grid(path)
    if found:
        return results.hand(align.describe(value, found["meter"], found["first"]))
    return results.hand(f"{value:.1f} BPM")


def run(paths, value=None, force=False):
    if value is not None:
        return set_by_hand(paths, value)
    for f in song.files(paths):
        saved = results.read(f, "tempo")
        if not force and saved and (saved.endswith(results.HAND) or align.parse(saved)):
            why = "set by hand" if saved.endswith(results.HAND) else "where the beats fall is known (song-wizard align)"
            print(f"  {saved.split()[0]:>6} BPM  {f.name}  {why}, kept (--force detects it again)")
            continue
        try:
            audio, _ = load(f, sr=44100, mono=True)
        except subprocess.CalledProcessError:
            print(f"  {'??':>6}      {f.name}  (could not read)")
            continue
        bpm, _, low, high, confidence = analyze(audio[0])
        note, _ = describe(bpm, low, high, confidence)
        print(f"  {bpm:6.1f} BPM  {f.name}  {note}")
        if song.kind(f.name) == "version":
            print("  (a version at another speed: not saved as the song's tempo)")
            continue
        print(f"Saved to {results.save(f, 'tempo', f'{bpm:.1f} BPM  {note}')}")
