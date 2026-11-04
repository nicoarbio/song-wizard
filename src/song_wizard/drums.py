"""song-wizard drums: what the drums play, detected and saved next to the song as "<song>.drums.json",
to print as a drum sheet, hear in the practice player and take to a DAW as MIDI.

The hits are found by ADTOF (Zehren, Alunno, Bientinesi), a model trained to transcribe drums in
real music, run on the whole song: kick, snare, toms, hi-hat and cymbals. ADTOF doesn't tell an
open hi-hat from a closed one, nor the ride from a crash: the song's drum kit stems (separate
--stem drumkit) do. A cymbal hit is a ride or a crash by which of those two stems sounds louder
right then, and a hi-hat hit is open when its stem keeps ringing after it. A song without those
stems gets them first.

The model isn't part of song-wizard: it has its own license (CC BY-NC-SA 4.0: credit its
authors, non-commercial use only). The first time, song-wizard asks before downloading it
(2.2 MB, from a fixed address, used only if its SHA-256 matches).

The times are kept as they were played; the sheet puts them on the click's grid (sixteenths), so
detecting needs the song's click (click.txt), as the chords do."""

import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np

from . import __version__, align, results, weights
from .audio import base_of, expand
from .audio import load as load_audio
from .paths import MODELS_DIR

SUFFIX = ".drums.json"
# What the sheet and the player know. hhopen: the hi-hat, open.
PARTS = ("kick", "snare", "toms", "hihat", "hhopen", "ride", "crash")
MAX_HITS = 50000

MODEL_PAGE = "https://huggingface.co/thebluescreen/adtof-drums-onnx"
MODEL_URL = MODEL_PAGE + "/resolve/d0e809bb1c1b6fe8a4a00c576852117a0636ab5a/adtof_frame_rnn.onnx"
MODEL_SHA256 = "189ca3c2bc7339a5f0fdc0bb11069d4bcc4fafabd142e945228c368c379b6227"
MODEL_FILE = "adtof-frame-rnn.onnx"
MODEL_SOURCE = "ADTOF Frame_RNN (Zehren, Alunno, Bientinesi; CC BY-NC-SA 4.0)"
NOTICE = ("Drum detection uses ADTOF, a model by M. Zehren, M. Alunno and P. Bientinesi that isn't part of "
          "song-wizard. Its license is CC BY-NC-SA 4.0: non-commercial use only, crediting its authors.\n"
          f"It's downloaded once (2.2 MB) from {MODEL_PAGE}")

# The model: audio at 44.1 kHz in, one activation per class every 10 ms out; a hit is a peak over
# its class's threshold (the authors' values).
SR = 44100
FPS = 100
CLASSES = ("kick", "snare", "toms", "hihat", "cymbal")
THRESHOLDS = (0.22, 0.24, 0.32, 0.22, 0.30)
# Its peaks come a little late or early by a fixed amount; measured against the click (at most this).
MAX_OFFSET = 0.04
# A hi-hat hit is open when its stem, 90-200 ms after, still has this much of the hit's level.
OPEN_RATIO = 0.5
KIT = ("hihat", "ride", "crash")


def path_for(song):
    song = Path(song)
    return song.with_name(song.stem + SUFFIX)


def stem_for(song, part):
    song = Path(song)
    stem = song.with_name(f"{base_of(song.name)} ({part}).wav")
    return stem if stem.is_file() else None


def load(song):
    try:
        return json.loads(path_for(song).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def clean(data):
    """The hits checked and trimmed to the expected shape; ValueError if it's wrong."""
    if not isinstance(data, dict) or not isinstance(data.get("hits"), list) or len(data["hits"]) > MAX_HITS:
        raise ValueError("drums")
    hits = []
    for h in data["hits"]:
        t, part = float(h["t"]), str(h["part"])
        if part not in PARTS or not 0 <= t <= 36000:
            raise ValueError("hit")
        hits.append({"t": round(t, 3), "part": part, "hand": bool(h.get("hand"))})
    hits.sort(key=lambda h: (h["t"], PARTS.index(h["part"])))
    click = data.get("click")
    if click is not None:
        click = {"bpm": float(click["bpm"]), "meter": str(click["meter"])[:8], "first": float(click["first"])}
    return {"hits": hits, "click": click, "source": str(data.get("source") or "")[:200]}


def save(song, data):
    data = clean(data)
    path = path_for(song)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=0), encoding="utf-8")
    os.replace(tmp, path)
    return data


def model_ready():
    return (MODELS_DIR / MODEL_FILE).is_file()


def model_path():
    return weights.fetch(MODEL_URL, MODEL_SHA256, MODEL_FILE, "drum model (ADTOF)", "2.2 MB", MODELS_DIR)


_session = None


def session():
    global _session
    if _session is None:
        import onnxruntime
        _session = onnxruntime.InferenceSession(str(model_path()), providers=["CPUExecutionProvider"])
    return _session


def activations(audio):
    """The model's activations for mono 44.1 kHz audio: (frames, 5), one frame every 10 ms."""
    out = session().run(None, {"waveform": np.asarray(audio, dtype=np.float32)[None, :]})[0]
    return out[0]


def peaks(a, threshold):
    """The times of the hits in one class's activations: peaks over the threshold that are the
    highest of their neighborhood (20 ms before, 10 ms after) and over the average of the 100 ms
    before; two closer than 30 ms are one."""
    out, last = [], -10
    for i in np.flatnonzero(a >= threshold):
        if a[i] < a[max(0, i - 2):i + 2].max() or a[i] < a[max(0, i - 10):i + 2].mean() or i - last <= 2:
            continue
        out.append(i)
        last = i
    return np.array(out, dtype=float) / FPS


def offset(times, click):
    """How late (or early) the hits come, by the median of how far they are from the click's
    sixteenths; 0 with too few to tell, and never more than MAX_OFFSET."""
    if len(times) < 20:
        return 0.0
    sixteenth = 60 / click["bpm"] / 4
    k = np.round((times - click["first"]) / sixteenth)
    off = float(np.median(times - click["first"] - k * sixteenth))
    return max(-MAX_OFFSET, min(MAX_OFFSET, off))


def envelope(stem, sr=22050, hop=128):
    import librosa
    audio, _ = load_audio(stem, sr=sr, mono=True)
    return librosa.feature.rms(y=audio[0], frame_length=512, hop_length=hop)[0], sr / hop


def level(env, rate, t, before=0.01, after=0.06):
    a, b = max(0, int(round((t - before) * rate))), int(round((t + after) * rate))
    return float(env[a:b].max(initial=0))


def cymbals(times, ride, crash):
    """Each cymbal hit, "ride" or "crash": the stem that sounds louder right then. Without
    those stems, they're all crashes."""
    if ride is None or crash is None:
        return ["crash"] * len(times)
    return ["ride" if level(*ride, t) > level(*crash, t) else "crash" for t in times]


def hihats(times, hat):
    """Each hi-hat hit, "hhopen" when its stem still rings 90-200 ms after (or until the next
    hit), else "hihat". Without the stem, they're all closed."""
    if hat is None:
        return ["hihat"] * len(times)
    env, rate = hat
    out = []
    for i, t in enumerate(times):
        peak = level(env, rate, t)
        end = min(t + 0.2, (times[i + 1] if i + 1 < len(times) else t + 1) - 0.01)
        start = min(t + 0.09, end - 0.02)
        tail = env[int(round(start * rate)):int(round(end * rate))]
        ratio = float(tail.mean()) / peak if len(tail) and peak > 0 else 0
        out.append("hhopen" if ratio > OPEN_RATIO else "hihat")
    return out


def detect(song, click):
    """The song's hits, as [{"t", "part", "hand"}], in time order."""
    audio, _ = load_audio(song, sr=SR, mono=True)
    act = activations(audio[0])
    found = {name: peaks(act[:, k], THRESHOLDS[k]) for k, name in enumerate(CLASSES)}
    late = offset(np.concatenate(list(found.values())), click)
    found = {name: t - late for name, t in found.items()}
    kit = {p: envelope(s) if (s := stem_for(song, p)) else None for p in KIT}
    hits = [(t, name) for name in ("kick", "snare", "toms") for t in found[name]]
    hits += zip(found["cymbal"], cymbals(found["cymbal"], kit["ride"], kit["crash"]))
    hits += zip(found["hihat"], hihats(found["hihat"], kit["hihat"]))
    return sorted(({"t": round(float(max(0.0, t)), 3), "part": p, "hand": False} for t, p in hits),
                  key=lambda h: (h["t"], PARTS.index(h["part"])))


def keep_hand(new, old):
    """The detected hits with the ones put in by hand kept (a detected one of the same drum
    within 50 ms of them goes)."""
    hand = [h for h in (old or {}).get("hits", []) if h.get("hand")]
    if not hand:
        return new
    near = lambda h: any(x["part"] == h["part"] and abs(x["t"] - h["t"]) < 0.05 for x in hand)
    return sorted([h for h in new if not near(h)] + hand, key=lambda h: (h["t"], PARTS.index(h["part"])))


def click_of(song):
    return align.parse(results.read(os.path.dirname(song), "click").get(os.path.basename(song)))


def agreed(accept):
    """Whether the model may be used: it's here already, or the user says yes (asked in a
    terminal, or --accept-model-license from the interface, which asks in the page)."""
    if model_ready():
        return True
    print(NOTICE)
    if accept:
        return True
    if not sys.stdin.isatty():
        print("Run it again with --accept-model-license to download it.")
        return False
    return input("Download it? [y/N] ").strip().lower() in ("y", "yes", "s", "si", "sí")


# ---------- MIDI ----------
# General MIDI drums (channel 10): what each part plays in any drum instrument.
GM = {"kick": 36, "snare": 38, "toms": 45, "hihat": 42, "hhopen": 46, "ride": 51, "crash": 49}
TICKS = 480


def vlq(n):
    out = [n & 0x7F]
    while n > 0x7F:
        n >>= 7
        out.append(0x80 | (n & 0x7F))
    return bytes(reversed(out))


def midi(data):
    """The hits as a MIDI file (bytes): one drum track at the click's tempo, starting with the
    song, each hit where it was played (not moved onto the grid)."""
    click = data.get("click") or {"bpm": 120.0, "meter": "4/4", "first": 0.0}
    bpm = click["bpm"]
    tick = lambda t: int(round(t * bpm / 60 * TICKS))
    num, _, den = str(click["meter"]).partition("/")
    try:
        num, den = int(num), int(den or 4)
    except ValueError:
        num, den = 4, 4
    events = [(0, b"\xff\x51\x03" + int(round(60_000_000 / bpm)).to_bytes(3, "big")),
              (0, b"\xff\x58\x04" + bytes([num, max(0, den.bit_length() - 1), 24, 8])),
              (0, b"\xff\x03" + vlq(len(b"Drums")) + b"Drums")]
    for h in data.get("hits", []):
        start = tick(h["t"])
        events.append((start, bytes([0x99, GM[h["part"]], 100])))
        events.append((start + TICKS // 4, bytes([0x89, GM[h["part"]], 0])))
    events.sort(key=lambda e: (e[0], e[1][0] == 0x99))  # note-offs before note-ons at the same time
    track, now = b"", 0
    for at, message in events:
        track += vlq(at - now) + message
        now = at
    track += b"\x00\xff\x2f\x00"
    return (b"MThd" + (6).to_bytes(4, "big") + (0).to_bytes(2, "big") + (1).to_bytes(2, "big") + TICKS.to_bytes(2, "big")
            + b"MTrk" + len(track).to_bytes(4, "big") + track)


def export(song, what, fold=True, lang="en"):
    """Writes "<song>.drums.html" (the sheet) or "<song>.drums.mid" next to the song."""
    from . import drumsheet
    data = load(song)
    if not data:
        sys.exit(f"{os.path.basename(song)} has no drums detected yet: song-wizard drums \"{song}\"")
    out = Path(song).with_name(Path(song).stem + (".drums.mid" if what == "midi" else ".drums.html"))
    if what == "midi":
        out.write_bytes(midi(data))
    else:
        out.write_text(drumsheet.page(base_of(Path(song).name), data, lang, fold), encoding="utf-8")
    return out


def run(paths, force=False, accept=False, sheet=False, as_midi=False, full=False):
    songs = list(expand(paths, skip_generated=True))
    if sheet or as_midi:
        for song in songs:
            for what in [w for w, on in (("sheet", sheet), ("midi", as_midi)) if on]:
                print(f"  wrote {export(song, what, fold=not full).name}")
        return
    if not songs or not agreed(accept):
        return
    for song in songs:
        name = os.path.basename(song)
        click = click_of(song)
        if click is None:
            print(f"  {name}: it has no click yet; finding its tempo and first beat first (align)")
            align.run([song])
            click = click_of(song)
            if click is None:
                print(f"  ??  {name}  (no steady beat found: set its click with song-wizard align --bpm --first)")
                continue
        if not all(stem_for(song, p) for p in KIT):
            print(f"  {name}: separating its drum kit first (to tell the ride from the crash, and the open hi-hat)")
            from . import separate
            separate.run(["drumkit"], [song])
        try:
            hits = detect(song, click)
        except subprocess.CalledProcessError:
            print(f"  ??  {name}  (could not read)")
            continue
        hits = keep_hand(hits, None if force else load(song))
        save(song, {"hits": hits, "click": click, "source": f"{MODEL_SOURCE}, song-wizard {__version__}"})
        count = {p: sum(h["part"] == p for h in hits) for p in PARTS}
        kept = sum(h["hand"] for h in hits)
        print(f"  {len(hits)} hits ({', '.join(f'{p} {n}' for p, n in count.items() if n)})  {name}"
              + (f"  ({kept} put in by hand, kept)" if kept else ""))
