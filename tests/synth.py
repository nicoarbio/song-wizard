"""Synthetic audio for the tests: nothing here comes from a real song."""

from pathlib import Path

import numpy as np
import soundfile as sf

SR = 44100
NOTE = {"C": 0, "C#": 1, "D": 2, "Eb": 3, "E": 4, "F": 5, "F#": 6, "G": 7, "Ab": 8, "A": 9, "Bb": 10, "B": 11}


def write(path, audio, sr=SR):
    """(channels, samples) or (samples,) float audio -> 32-bit float WAV."""
    audio = np.atleast_2d(np.asarray(audio, dtype=np.float32))
    sf.write(str(path), audio.T, sr, subtype="FLOAT")
    return path


def song(folder, name, audio, sr=SR):
    """A song as song-wizard keeps it: folder/<name without extension>/<name>, as a WAV."""
    here = Path(folder) / Path(name).stem
    here.mkdir(parents=True, exist_ok=True)
    return write(here / name, audio, sr)


def sine(freq, seconds, peak=0.5, channels=2):
    t = np.arange(int(seconds * SR)) / SR
    return np.tile(peak * np.sin(2 * np.pi * freq * t), (channels, 1)).astype(np.float32)


def midi_freq(midi):
    return 440 * 2 ** ((midi - 69) / 12)


def tone(midi, seconds, harmonics=6):
    """A plucked, slightly bright note: a few decaying harmonics."""
    t = np.arange(int(seconds * SR)) / SR
    f = midi_freq(midi)
    out = sum(np.sin(2 * np.pi * f * h * t) / h for h in range(1, harmonics + 1) if f * h < SR / 2)
    return out * np.exp(-t * 1.5)


def chord_song(key="G", minor=False, bars=16, bpm=100):
    """I-IV-V-I (or i-iv-V-i in minor) with a bass line and a melody on the scale, mono."""
    root = 48 + NOTE[key]  # around C3
    scale = [0, 2, 3, 5, 7, 8, 10] if minor else [0, 2, 4, 5, 7, 9, 11]
    # (offset from the key, minor chord?) for each chord of the progression.
    progression = [(0, minor), (5, minor), (7, False), (0, minor)]
    bar = 4 * 60 / bpm
    out = np.zeros(int(bars * bar * SR) + SR)
    for b in range(bars):
        offset, chord_minor = progression[b % 4]
        start = int(b * bar * SR)
        notes = [root + offset, root + offset + (3 if chord_minor else 4), root + offset + 7]
        chord = sum(tone(n + 12, bar) for n in notes) + 1.5 * tone(root + offset - 12, bar)
        out[start:start + len(chord)] += chord
        for beat in range(4):  # melody: one scale note per beat, an octave up
            degree = scale[(b * 4 + beat) % 7]
            n = tone(root + 24 + degree, bar / 4)
            s = start + int(beat * bar / 4 * SR)
            out[s:s + len(n)] += 0.6 * n
    return (0.8 * out / np.abs(out).max()).astype(np.float32)


def drum_song(bpm=120, bars=32, seed=0):
    """Rock beat: kick on 1 and 3, snare on 2 and 4, hi-hat on eighths. Mono."""
    rng = np.random.default_rng(seed)
    beat = 60 / bpm
    out = np.zeros(int(bars * 4 * beat * SR) + SR)

    def hit(at, sound):
        i = int(round(at * SR))
        out[i:i + len(sound)] += sound

    t = np.arange(int(0.25 * SR)) / SR
    kick = np.sin(2 * np.pi * (50 + 100 * np.exp(-t * 30)) * t) * np.exp(-t * 12)
    snare = (0.6 * rng.standard_normal(len(t)) + 0.4 * np.sin(2 * np.pi * 190 * t)) * np.exp(-t * 20)
    th = t[:int(0.05 * SR)]
    hat = 0.25 * rng.standard_normal(len(th)) * np.exp(-th * 80)
    for k in range(bars * 4):
        at = k * beat
        hit(at, kick if k % 2 == 0 else snare)
        hit(at, hat)
        hit(at + beat / 2, hat)
    return (0.8 * out / np.abs(out).max()).astype(np.float32)


def dominant_freq(mono, sr=SR):
    spectrum = np.abs(np.fft.rfft(mono * np.hanning(len(mono))))
    return np.fft.rfftfreq(len(mono), 1 / sr)[np.argmax(spectrum)]
