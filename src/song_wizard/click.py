"""Click track with a count-in, following the song's beats (or a steady grid).

The count-in goes before bar 1, so the song (and any stems of it next to it) get the same
silence added at the start: every "(count-in)" file and the click start together.
"""

import os
import re

import numpy as np
import soundfile as sf

from .audio import die, expand, load, output_path, save
from .bpm import analyze, describe

CLICK_SECONDS = 0.03
ACCENT_HZ, BEAT_HZ = 1500, 1000
ACCENT_GAIN, BEAT_GAIN = 0.7, 0.45
# Stems of a song that get the count-in silence too, if they exist next to it.
STEM_SUFFIXES = ["vocals", "drums", "bass", "guitar", "other",
                 "no vocals", "no drums", "no bass", "no guitar"]
ANALYSIS_SR = 44100


def parse_meter(meter):
    match = re.fullmatch(r"\s*(\d+)\s*/\s*(\d+)\s*", str(meter))
    if not match or not 1 <= int(match.group(1)) <= 32:
        die(f'Invalid meter "{meter}": use something like 4/4, 3/4, 6/8 or 7/8.')
    return int(match.group(1))


def beat_features(audio, beats):
    """Per beat: bass energy right after it (kick, bass notes) and how much the harmony
    changes from the previous beat. Both tend to peak on the first beat of the bar."""
    from scipy.signal import butter, sosfilt

    sr = ANALYSIS_SR
    low = sosfilt(butter(4, 150, "low", fs=sr, output="sos"), audio)
    idx = (beats * sr).astype(int)
    bass = np.array([np.sqrt(np.mean(low[i:i + int(0.1 * sr)] ** 2) + 1e-12) for i in idx])

    freqs = np.fft.rfftfreq(4096, 1 / sr)
    band = (freqs > 55) & (freqs < 2000)
    pitch_class = (np.round(12 * np.log2(freqs[band] / 440)) % 12).astype(int)
    chroma = []
    for start, end in zip(idx, list(idx[1:]) + [len(audio)]):
        seg = audio[start:max(end, start + 1)][:4096]
        spec = np.abs(np.fft.rfft(seg * np.hanning(len(seg)), 4096))[band]
        c = np.bincount(pitch_class, weights=spec, minlength=12)
        chroma.append(c / (np.linalg.norm(c) + 1e-12))
    chroma = np.array(chroma)
    change = np.r_[0, 1 - np.sum(chroma[1:] * chroma[:-1], axis=1)]
    return bass, change


ONSET_FRAME, ONSET_HOP = 512, 64


def onset_strength(audio):
    """High-frequency-content onset function (the most precise one for drum hits), one value
    per hop, timed at the centre of each frame."""
    import essentia.standard as es

    window, fft, polar = es.Windowing(type="hann"), es.FFT(), es.CartesianToPolar()
    detect = es.OnsetDetection(method="hfc")
    values = np.array([detect(*polar(fft(window(frame))))
                       for frame in es.FrameGenerator(audio, frameSize=ONSET_FRAME, hopSize=ONSET_HOP,
                                                      startFromZero=True)])
    times = (np.arange(len(values)) * ONSET_HOP + ONSET_FRAME / 2) / ANALYSIS_SR
    return times, values


def music_start(audio):
    """First moment the audio is louder than -40 dB below its loudest 50 ms."""
    sr = ANALYSIS_SR
    hop = sr // 20
    frames = len(audio) // hop
    rms = np.sqrt(np.mean(audio[: frames * hop].reshape(frames, hop) ** 2, axis=1))
    return float(np.argmax(rms > 0.01 * rms.max()) * hop / sr)


def refine_beats(audio, beats):
    """Essentia's beats land 10-30 ms after the actual hits, enough to hear against a click,
    and before it locks on it can place beats where nothing is played (a silence, a fade-in,
    a soft intro). Each beat is moved to the strongest attack just before it; the beats before
    the first 4 that land on real hits are rebuilt from those, but never before the music."""
    times, strength = onset_strength(audio)
    strong = 0.05 * np.percentile(strength, 99)
    per_second = ANALYSIS_SR / ONSET_HOP

    def snap(b, before=0.07, after=0.02):
        lo = max(0, int((b - before) * per_second))
        hi = min(len(strength), int((b + after) * per_second) + 1)
        if hi <= lo:
            return b, False
        j = lo + int(np.argmax(strength[lo:hi]))
        return (times[j], True) if strength[j] > strong else (b, False)

    snapped = [snap(b) for b in beats]
    hit = np.array([ok for _, ok in snapped])
    # Beats without a clear attack (held notes, breaks) get the typical correction.
    moved = [t - b for (t, ok), b in zip(snapped, beats) if ok]
    typical = float(np.median(moved)) if moved else 0.0
    beats = np.array([t if ok else t + typical for t, ok in snapped])

    # Real beats are kept as they are, even if the intro has its own tempo. Only a run of
    # beats with no hits at the very start is replaced, continuing the pace of the first
    # 4 beats that do land on hits.
    first = next((i for i in range(len(beats) - 3) if hit[i:i + 4].all()), 0)
    if first:
        pace = float(np.median(np.diff(beats[first:first + 9])))
        start = music_start(audio)
        back = beats[first] - pace * np.arange(int((beats[first] - start) / pace) + 1, 0, -1)
        back = [snap(t, 0.04, 0.04)[0] for t in back if t >= start - 0.03]
        beats = np.r_[back, beats[first:]]
    return beats


def downbeat_phase(audio, beats, per_bar):
    """Index (0..per_bar-1) of the first detected beat that starts a bar."""
    if per_bar == 1 or len(beats) < 2 * per_bar:
        return 0
    bass, change = beat_features(audio, beats)
    z = lambda x: (x - x.mean()) / (x.std() + 1e-12)
    score = z(np.log(bass)) + z(change)
    return int(np.argmax([score[p::per_bar].mean() for p in range(per_bar)]))


def click_sound(sr, accent):
    t = np.arange(int(CLICK_SECONDS * sr)) / sr
    freq, gain = (ACCENT_HZ, ACCENT_GAIN) if accent else (BEAT_HZ, BEAT_GAIN)
    return (gain * np.sin(2 * np.pi * freq * t) * np.exp(-t / 0.006)).astype(np.float32)


def run(paths, meter, count_in, steady=False, shift=0):
    per_bar = parse_meter(meter)
    if count_in < 0:
        die("--count-in must be 0 or more bars.")

    for f in expand(paths, skip_generated=True):
        mono, _ = load(f, sr=ANALYSIS_SR, mono=True)
        bpm, beats, low, high, confidence = analyze(mono[0])
        if len(beats) < 4:
            print(f"  skipping {os.path.basename(f)}: no beat found")
            continue
        note, trusted = describe(bpm, low, high, confidence)
        duration = mono.shape[1] / ANALYSIS_SR
        beats = refine_beats(mono[0], beats[beats < duration])

        # Bar 1 is found on the real beats, also for a steady click: a straight grid can be
        # off at the start of a song that drifts.
        first = (downbeat_phase(mono[0], beats, per_bar) + shift) % per_bar

        if steady:
            # Best straight line through the detected beats: one tempo for the whole song.
            k = np.arange(len(beats))
            interval, offset = np.polyfit(k, beats, 1)
            grid = offset + interval * np.arange(-len(beats), int((duration - offset) / interval) + 1)
            grid = grid[grid >= 0]
            song_beats = grid[int(np.argmin(np.abs(grid - beats[first]))):]
            lead_interval = interval
        else:
            lead_interval = float(np.median(np.diff(beats[first:first + 9])))
            tail = float(np.median(np.diff(beats[-9:])))
            extra = beats[-1] + tail * np.arange(1, int((duration - beats[-1]) / tail) + 1)
            song_beats = np.r_[beats, extra][first:]

        bar1 = song_beats[0]
        positions = np.arange(len(song_beats)) % per_bar

        # Count-in: count_in bars at the opening tempo, leading straight into bar 1.
        lead = count_in * per_bar
        lead_times = bar1 - lead_interval * np.arange(lead, 0, -1)
        pad = max(0.0, -float(lead_times[0])) if lead else 0.0
        times = np.r_[lead_times, song_beats] + pad
        accents = np.r_[np.arange(lead) % per_bar == 0, positions == 0]

        audio, sr = load(f)
        out_len = audio.shape[1] + round(pad * sr)
        track = np.zeros(out_len, dtype=np.float32)
        sounds = {True: click_sound(sr, True), False: click_sound(sr, False)}
        for t, accent in zip(times, accents):
            i = round(t * sr)
            s = sounds[bool(accent)][: max(0, out_len - i)]
            track[i:i + len(s)] += s
        save(output_path(f, "click"), np.vstack([track, track]), sr)

        written = [output_path(f, "click")]
        # Written even when no silence is needed (the song has room before bar 1), so every
        # song always gets the same set of files that start together.
        written.append(padded(audio, sr, pad, output_path(f, "count-in")))
        for suffix in STEM_SUFFIXES:
            stem = output_path(f, suffix)
            if os.path.exists(stem):
                stem_audio, stem_sr = sf.read(stem, dtype="float32", always_2d=True)
                written.append(padded(stem_audio.T, stem_sr, pad,
                                      f"{os.path.splitext(stem)[0]} (count-in).wav"))

        mode = "steady grid" if steady else "follows the song"
        print(f"  {bpm:6.1f} BPM  {meter}  count-in {count_in} bar{'s' if count_in != 1 else ''}  "
              f"bar 1 at {bar1:.2f} s  click {mode}  {os.path.basename(f)}")
        if not trusted:
            print(f"           tempo {note}: check the click against the song")
        elif steady and note != "steady":
            print(f"           tempo {note}: a steady click will drift from the recording")
        for w in written:
            print(f"           {w}")


def padded(audio, sr, pad, out):
    silence = np.zeros((audio.shape[0], round(pad * sr)), dtype=np.float32)
    save(out, np.concatenate([silence, audio], axis=1), sr)
    return out
