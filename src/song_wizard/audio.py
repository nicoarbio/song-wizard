"""Audio I/O helpers. Decoding always goes through the system ffmpeg, so every
format it understands (Opus, WebM, M4A, MP3...) works everywhere."""

import os
import re
import shutil
import subprocess
import sys

import numpy as np
import soundfile as sf

AUDIO_EXTS = {".opus", ".webm", ".wav", ".flac", ".mp3", ".m4a", ".ogg", ".aac", ".mkv", ".mp4", ".aiff", ".aif"}

# Files this tool writes: "Title (drums).wav", "Title (no drums).wav", "Title (other).wav",
# "Title (+2).wav", "Title (click).wav", "Title (count-in).wav" and "Title (drums) (count-in).wav".
GENERATED = re.compile(r" \(((no )?(vocals|drums|bass|guitar)|other|[+-]\d+(\.\d+)?|click)\)( \(count-in\))?$"
                       r"| \(count-in\)$")


def die(msg):
    print(msg, file=sys.stderr)
    sys.exit(1)


def require_ffmpeg():
    if not shutil.which("ffmpeg"):
        die('ffmpeg is missing. Run "song-wizard setup" to see how to install it.')


def expand(paths, skip_generated=False):
    """Expand folders into the audio files they contain (non-recursive, sorted). With
    skip_generated, files this tool wrote (stems, clicks...) are left out of folders; files
    named explicitly are always kept."""
    for p in paths:
        if os.path.isdir(p):
            for name in sorted(os.listdir(p)):
                stem, ext = os.path.splitext(name)
                if ext.lower() not in AUDIO_EXTS:
                    continue
                if skip_generated and GENERATED.search(stem):
                    continue
                yield os.path.join(p, name)
        elif os.path.isfile(p):
            yield p
        else:
            print(f"  skipping {p}: not found", file=sys.stderr)


def load(path, sr=None, mono=False):
    """Decode any file to float32, shape (channels, samples). Returns (audio, sample_rate)."""
    require_ffmpeg()
    if sr is None:
        sr = probe_sample_rate(path)
    channels = 1 if mono else 2
    cmd = ["ffmpeg", "-nostdin", "-v", "error", "-i", path, "-vn",
           "-ac", str(channels), "-ar", str(sr), "-f", "f32le", "-"]
    raw = subprocess.run(cmd, capture_output=True, check=True).stdout
    audio = np.frombuffer(raw, dtype=np.float32).reshape(-1, channels).T.copy()
    return audio, sr


def probe_sample_rate(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries", "stream=sample_rate",
         "-of", "default=nw=1:nk=1", path],
        capture_output=True, text=True, check=True).stdout.strip()
    return int(out or 44100)


def save(path, audio, sr):
    """Write (channels, samples) float audio as 32-bit float WAV: peaks above 0 dB are kept."""
    sf.write(path, audio.T, sr, subtype="FLOAT")


def output_path(src, suffix):
    """'dir/Title.opus' + 'drums' -> 'dir/Title (drums).wav'"""
    return f"{os.path.splitext(src)[0]} ({suffix}).wav"
