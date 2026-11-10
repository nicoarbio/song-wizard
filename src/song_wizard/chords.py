"""song-wizard chords: the chords of a song, detected and saved next to it as "<song>.chords.json",
to read along in the practice player and correct by hand.

The detection is BTC (third_party/btc), on the whole song. Its changes are moved onto the song's
beats, so it needs the song's click (click.txt: its exact tempo and first beat), which `align`
finds; if the song has none, it's found first. Chords corrected by hand are kept when detecting
again, unless --force.

The model's weights (12 MB) are downloaded once from a fixed address and used only if their
SHA-256 matches; they're opened as numbers only (torch's weights_only), allowing just the two
numpy types they hold (the normalization's mean and standard deviation)."""

import json
import os
import re
import subprocess

from . import __version__, align, weights
from . import song as songfs
from .audio import load as load_audio
from .paths import MODELS_DIR

MODEL_URL = ("https://raw.githubusercontent.com/jayg996/BTC-ISMIR19/2682317be668032e6e4b269ded36adaa2ad57df0/"
             "test/btc_model_large_voca.pt")
MODEL_SHA256 = "1673d23f8f9a55ae7f9e8b80a51da616debb22675b8d8b67ea6ce0ef37b0ab51"
MODEL_FILE = "btc-large-voca.pt"
MAX_CHORDS = 5000
MAX_NAME = 24

# BTC's qualities as they're usually written on a chord sheet.
QUALITY = {"maj": "", "min": "m", "dim": "dim", "aug": "aug", "min6": "m6", "maj6": "6", "min7": "m7",
           "minmaj7": "m(maj7)", "maj7": "maj7", "7": "7", "dim7": "dim7", "hdim7": "m7b5", "sus2": "sus2",
           "sus4": "sus4"}
NO_CHORD = "N.C."
NOTE = r"[A-G](?:#|b)?"
# What the page and the terminal understand as a chord (anything else is still saved, with a
# warning: it just isn't transposed or simplified).
CHORD = re.compile(rf"^(?P<root>{NOTE})(?P<quality>maj|min|m|dim|aug|\+|°|ø|sus[24]?|add)?"
                   rf"(?P<extra>[0-9b#()majdsu+]*)(?:/(?P<bass>{NOTE}))?$")


def path_for(song):
    return songfs.data(song, "chords")


def understood(name):
    """Whether song-wizard can read this name as a chord (to transpose or simplify it)."""
    return name == NO_CHORD or bool(CHORD.match(name))


def load(song):
    path = path_for(song)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def clean(data):
    """What the page sent, checked and trimmed to the expected shape; ValueError if it's wrong.
    A name that isn't a chord is allowed (the page warns about it); only the shape is enforced."""
    if not isinstance(data, dict) or not isinstance(data.get("chords"), list) or len(data["chords"]) > MAX_CHORDS:
        raise ValueError("chords")
    chords = []
    for c in data["chords"]:
        start, end, name = float(c["from"]), float(c["to"]), str(c["name"]).strip()[:MAX_NAME]
        if not 0 <= start < end <= 36000 or not name:
            raise ValueError("chord")
        chords.append({"from": round(start, 3), "to": round(end, 3), "name": name, "hand": bool(c.get("hand"))})
    chords.sort(key=lambda c: c["from"])
    for a, b in zip(chords, chords[1:]):
        if b["from"] < a["to"] - 0.001:
            raise ValueError("overlap")
    click = data.get("click")
    if click is not None:
        click = {"bpm": float(click["bpm"]), "meter": str(click["meter"])[:8], "first": float(click["first"])}
    return {"chords": chords, "click": click, "source": str(data.get("source") or "")[:200]}


def save(song, data):
    data = clean(data)
    path = path_for(song)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, path)
    return data


def model_path():
    """The model's weights, downloaded and checked the first time. Exits if they don't match."""
    return weights.fetch(MODEL_URL, MODEL_SHA256, MODEL_FILE, "chord model", "12 MB", MODELS_DIR)


_model = None


def model():
    """(model, mean, std, device), loaded once."""
    global _model
    if _model is None:
        import numpy as np
        import torch

        from .third_party.btc.model import BTC_model
        torch.serialization.add_safe_globals([(np._core.multiarray.scalar, "numpy.core.multiarray.scalar"), np.dtype,
                                              np.dtypes.Float64DType, np.dtypes.Float32DType])
        checkpoint = torch.load(model_path(), weights_only=True, map_location="cpu")
        device = "cuda" if torch.cuda.is_available() else "cpu"
        net = BTC_model()
        net.load_state_dict(checkpoint["model"])
        _model = (net.to(device), checkpoint["mean"], checkpoint["std"], device)
    return _model


def pretty(label):
    """BTC's label as written on a chord sheet: "A:min7" -> "Am7", "N" -> "N.C."."""
    if label in ("N", "X"):
        return NO_CHORD
    root, _, quality = label.partition(":")
    return root + QUALITY.get(quality or "maj", quality)


def on_beats(found, click, end):
    """BTC's chords moved onto the click's beats: each change to the nearest beat, and a chord
    shorter than half a beat dropped (it's a passing moment, or a detection flicker)."""
    beat = 60 / click["bpm"]
    snap = lambda t: max(0.0, click["first"] + round((t - click["first"]) / beat) * beat)
    out = []
    for start, stop, label in found:
        name = pretty(label)
        start, stop = snap(start), min(snap(stop), end)
        if stop - start < beat / 2:
            continue
        if out and out[-1]["name"] == name and abs(out[-1]["to"] - start) < 0.01:
            out[-1]["to"] = round(stop, 3)
            continue
        if out and start < out[-1]["to"]:
            start = out[-1]["to"]
        if stop - start < beat / 2:
            continue
        if out and start > out[-1]["to"] + 0.001:  # a dropped bit: the previous chord lasts until here
            out[-1]["to"] = round(start, 3)
        out.append({"from": round(start, 3), "to": round(stop, 3), "name": name, "hand": False})
    if out and out[0]["from"] > 0.001 and out[0]["name"] == NO_CHORD:
        out[0]["from"] = 0.0
    return out


def keep_hand(new, old):
    """The detected chords with the ones corrected by hand put back over them."""
    hand = [c for c in (old or {}).get("chords", []) if c.get("hand")]
    if not hand:
        return new
    out = []
    for c in new:
        pieces = [(c["from"], c["to"])]
        for h in hand:
            pieces = [p for a, b in pieces
                      for p in ((a, min(b, h["from"])), (max(a, h["to"]), b)) if p[1] - p[0] > 0.05]
        out += [{**c, "from": round(a, 3), "to": round(b, 3)} for a, b in pieces]
    return sorted(out + hand, key=lambda c: c["from"])


def detect(song, click):
    """The song's chords on its beats."""
    from .third_party.btc import model as btc

    net, mean, std, device = model()
    audio, _ = load_audio(song, sr=btc.SAMPLE_RATE, mono=True)
    found = btc.chords(net, mean, std, audio[0], device)
    return on_beats(found, click, len(audio[0]) / btc.SAMPLE_RATE)


def click_of(song):
    return align.grid(song)


def run(paths, force=False):
    for song in songfs.expand(paths):
        name = os.path.basename(song)
        click = click_of(song)
        if click is None:
            print(f"  {name}: it has no click yet; finding its tempo and first beat first (align)")
            align.run([song])
            click = click_of(song)
            if click is None:
                print(f"  ??  {name}  (no steady beat found: set its click with song-wizard align --bpm --first)")
                continue
        try:
            chords = detect(song, click)
        except subprocess.CalledProcessError:
            print(f"  ??  {name}  (could not read)")
            continue
        old = None if force else load(song)
        chords = keep_hand(chords, old)
        kept = sum(c["hand"] for c in chords)
        save(song, {"chords": chords, "click": click,
                    "source": f"BTC (large vocabulary), song-wizard {__version__}"})
        names = sorted({c["name"] for c in chords if c["name"] != NO_CHORD})
        print(f"  {len(chords)} chords ({', '.join(names[:12])}{'...' if len(names) > 12 else ''})  {name}"
              + (f"  ({kept} corrected by hand, kept)" if kept else ""))
