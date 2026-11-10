"""song-wizard notes: the notes the bass and the voice play, from their separated stems, saved next to
the song as "<song>.notes.json", to read (and hear) in the practice player and correct by hand.

The bass's are followed with pYIN (in librosa); the voice's with CREPE (third_party/crepe), which
copes better with a voice's vibrato and slides. Both are one line at a time: where several voices
sing at once (backing vocals) it follows one of them. Notes in the stem's near-silence (bleed from
the other instruments) and notes far from the rest of the part are dropped. Notes corrected by hand
are kept when detecting again, unless --force.

CREPE's model (89 MB) is downloaded once from a fixed address, used only if its SHA-256 matches and
opened as numbers only (torch's weights_only)."""

import json
import os
import subprocess

import numpy as np

from . import __version__, weights
from . import song as songfs
from .audio import load as load_audio
from .paths import MODELS_DIR

PARTS = ("bass", "vocals")
CREPE_URL = ("https://raw.githubusercontent.com/maxrmorrison/torchcrepe/745670a18bf8c5f1a2f08c910c72433badde3e08/"
             "torchcrepe/assets/full.pth")
CREPE_SHA256 = "133225604dedd2e4005f8bbd1bd0a2ec073ba8b7a6cd31ff6d5edbbfa3539986"
CREPE_FILE = "crepe-full.pth"
MAX_NOTES = 20000
NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def path_for(song):
    return songfs.data(song, "notes")


def stem_for(song, part):
    """The song's separated stem for that part ("bass.opus"), or None."""
    return songfs.stem(song, part)


def name(midi):
    return f"{NAMES[midi % 12]}{midi // 12 - 1}"


def load(song):
    try:
        return json.loads(path_for(song).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def clean(data):
    """What the page sent, checked: {part: {"notes": [{from, to, midi, hand}], "source"}}."""
    if not isinstance(data, dict):
        raise ValueError("notes")
    out = {}
    for part, value in data.items():
        if part not in PARTS or not isinstance(value, dict) or not isinstance(value.get("notes"), list) \
                or len(value["notes"]) > MAX_NOTES:
            raise ValueError("part")
        notes = []
        for n in value["notes"]:
            start, end, midi = float(n["from"]), float(n["to"]), int(n["midi"])
            if not 0 <= start < end <= 36000 or not 0 <= midi <= 127:
                raise ValueError("note")
            notes.append({"from": round(start, 3), "to": round(end, 3), "midi": midi, "hand": bool(n.get("hand"))})
        notes.sort(key=lambda n: n["from"])
        out[part] = {"notes": notes, "source": str(value.get("source") or "")[:200]}
    return out


def save(song, data):
    data = clean(data)
    path = path_for(song)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, path)
    return data


def segment(times, midi, step, min_len, gap=0.06):
    """Notes from a pitch line (one MIDI number or NaN per frame): runs of the same note, the same
    note across a gap shorter than `gap` joined, and then those shorter than `min_len` dropped."""
    runs, start = [], 0
    for i in range(1, len(midi) + 1):
        if i == len(midi) or midi[i] != midi[start] or np.isnan(midi[i]) != np.isnan(midi[start]):
            if not np.isnan(midi[start]):
                runs.append([float(times[start]), float(times[i - 1] + step), int(midi[start])])
            start = i
    joined = []
    for r in runs:
        if joined and joined[-1][2] == r[2] and r[0] - joined[-1][1] < gap:
            joined[-1][1] = r[1]
        else:
            joined.append(r)
    return [{"from": round(a, 3), "to": round(b, 3), "midi": m, "hand": False}
            for a, b, m in joined if b - a >= min_len - 1e-6]


def keep_loud(midi, audio, sr, hop, below=35):
    """Frames far quieter than the stem's loud parts (bleed, silence) lose their note; so do notes
    more than an octave and a half from the part's middle note."""
    import librosa

    rms = librosa.feature.rms(y=audio, frame_length=1024, hop_length=hop, center=True)[0]
    rms = np.pad(rms, (0, max(0, len(midi) - len(rms))))[: len(midi)]
    db = 20 * np.log10(rms + 1e-9)
    midi = np.where(db > np.percentile(db, 95) - below, midi, np.nan)
    if np.isfinite(midi).any():
        middle = np.nanmedian(midi)
        midi[np.abs(midi - middle) > 18] = np.nan
    return midi


def bass_notes(stem):
    import librosa

    sr, hop = 22050, 256
    audio, _ = load_audio(str(stem), sr=sr, mono=True)
    y = audio[0]
    f0, voiced, _ = librosa.pyin(y, fmin=35, fmax=300, sr=sr, frame_length=2048, hop_length=hop)
    midi = np.where(voiced, np.round(librosa.hz_to_midi(np.nan_to_num(f0, nan=1.0))), np.nan)
    midi = keep_loud(midi, y, sr, hop)
    times = librosa.times_like(midi, sr=sr, hop_length=hop)
    return segment(times, midi, hop / sr, 0.08)


_crepe = None


def vocal_notes(stem):
    import torch

    from .third_party.crepe import model as crepe

    global _crepe
    if _crepe is None:
        net = crepe.Crepe()
        path = weights.fetch(CREPE_URL, CREPE_SHA256, CREPE_FILE, "voice model", "89 MB", MODELS_DIR)
        net.load_state_dict(torch.load(path, weights_only=True, map_location="cpu"))
        device = "cuda" if torch.cuda.is_available() else "cpu"
        _crepe = (net.to(device), device)
    net, device = _crepe
    hop = 160
    audio, _ = load_audio(str(stem), sr=crepe.SAMPLE_RATE, mono=True)
    y = audio[0]
    f0, confidence = crepe.pitch(net, y, hop=hop, device=device)
    # As torchcrepe's filters: the confidence's median and the pitch's mean over three frames.
    confidence = np.array([np.median(confidence[max(0, i - 1): i + 2]) for i in range(len(confidence))])
    f0 = np.convolve(np.pad(f0, 1, mode="edge"), np.ones(3) / 3, mode="valid")
    midi = np.where(confidence > 0.5, np.round(12 * np.log2(f0 / 440) + 69), np.nan)
    midi = keep_loud(midi, y, crepe.SAMPLE_RATE, hop)
    times = np.arange(len(midi)) * hop / crepe.SAMPLE_RATE
    return segment(times, midi, hop / crepe.SAMPLE_RATE, 0.1)


DETECT = {"bass": (bass_notes, "pYIN"), "vocals": (vocal_notes, "CREPE")}


def keep_hand(new, old):
    """The detected notes with the ones corrected by hand put back (a detected note overlapping one
    corrected by hand goes)."""
    hand = [n for n in (old or {}).get("notes", []) if n.get("hand")]
    kept = [n for n in new if not any(n["from"] < h["to"] and h["from"] < n["to"] for h in hand)]
    return sorted(kept + hand, key=lambda n: n["from"])


def run(paths, part=None, force=False):
    parts = [part] if part else list(PARTS)
    for song in songfs.expand(paths):
        title = os.path.basename(song)
        stems = {p: stem_for(song, p) for p in parts}
        if not any(stems.values()):
            print(f"  ??  {title}  (it has no {' or '.join(parts)} stem: separate it first, "
                  f"song-wizard separate --stem {parts[0]})")
            continue
        data = load(song) or {}
        said = []
        for p, stem in stems.items():
            if not stem:
                continue
            detect, how = DETECT[p]
            try:
                found = detect(stem)
            except subprocess.CalledProcessError:
                said.append(f"{p}: could not read its stem")
                continue
            found = keep_hand(found, None if force else data.get(p))
            data[p] = {"notes": found, "source": f"{how}, song-wizard {__version__}"}
            kept = sum(n["hand"] for n in found)
            said.append(f"{p}: {len(found)} notes" + (f" ({kept} corrected by hand, kept)" if kept else ""))
        save(song, data)
        print(f"  {'; '.join(said)}  {title}")
