"""Convert to a small, widely playable format (MP3 or M4A) to share, e.g. over WhatsApp."""

import os
import subprocess

import numpy as np

from .audio import expand, load, require_ffmpeg

FORMATS = {
    # LAME VBR quality 2 is ~190 kbps: transparent for practice tracks, ~7 MB for 5 minutes.
    "mp3": ["-c:a", "libmp3lame", "-q:a", "2", "-id3v2_version", "3"],
    "m4a": ["-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart"],
}
# Folders: only lossless files are converted, so nothing lossy gets re-encoded and an .opus and
# a .wav of the same song don't both turn into the same .mp3.
LOSSLESS = {".wav", ".flac", ".aif", ".aiff"}
# Lossy formats clip whatever goes above 0 dB when played, and encoding itself adds a little
# to the peaks, so louder files are turned down to -1 dB first (the usual margin for MP3/AAC).
MAX_PEAK = 10 ** (-1 / 20)


def run(paths, fmt="mp3", overwrite=False):
    require_ffmpeg()
    files = []
    for p in paths:
        if os.path.isdir(p):
            files += [f for f in expand([p]) if os.path.splitext(f)[1].lower() in LOSSLESS]
        else:
            files += list(expand([p]))

    for f in files:
        out = f"{os.path.splitext(f)[0]}.{fmt}"
        if os.path.abspath(out) == os.path.abspath(f):
            print(f"  skipping {os.path.basename(f)}: already {fmt}")
            continue
        if os.path.exists(out) and not overwrite:
            print(f"  skipping {os.path.basename(f)}: {os.path.basename(out)} already exists (--overwrite to replace)")
            continue

        audio, _ = load(f)
        peak = float(np.abs(audio).max()) if audio.size else 0.0
        gain = MAX_PEAK / peak if peak > MAX_PEAK else 1.0
        cmd = ["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", f, "-vn", "-map_metadata", "0"]
        if gain < 1.0:
            cmd += ["-af", f"volume={gain:.6f}"]
        subprocess.run([*cmd, *FORMATS[fmt], out], check=True)

        size = os.path.getsize(out) / 1e6
        note = f"  (turned down {20 * np.log10(gain):.1f} dB so the peaks don't clip)" if gain < 1.0 else ""
        print(f"  {size:5.1f} MB  {out}{note}")
