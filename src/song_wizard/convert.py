"""Convert to a small, widely playable format (MP3 or M4A) to share, e.g. over WhatsApp."""

import os
import subprocess

import numpy as np

from . import song, tags
from .audio import expand, load, require_ffmpeg

FORMATS = {
    # LAME VBR quality 2 is ~190 kbps: transparent for practice tracks, ~7 MB for 5 minutes.
    "mp3": ["-c:a", "libmp3lame", "-q:a", "2", "-id3v2_version", "3"],
    "m4a": ["-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart"],
}
# Folders: lossless files, and the stems and versions song-wizard made in Opus (its default), but
# not the downloaded .opus files, so a song isn't re-encoded for nothing; and an .opus and a .wav of
# the same file don't both turn into the same .mp3 (the .wav goes).
LOSSLESS = {".wav", ".flac", ".aif", ".aiff"}


def in_folder(f):
    """Whether converting a folder takes this file."""
    stem, ext = os.path.splitext(f)
    if ext.lower() in LOSSLESS:
        return True
    return (ext.lower() == ".opus" and song.parts(f) is not None
            and not any(os.path.exists(stem + e) for e in LOSSLESS))
# Lossy formats clip whatever goes above 0 dB when played, and encoding itself adds a little
# to the peaks, so louder files are turned down to -1 dB first (the usual margin for MP3/AAC).
MAX_PEAK = 10 ** (-1 / 20)


def run(paths, fmt="mp3", overwrite=False):
    require_ffmpeg()
    files = []
    for p in paths:
        if os.path.isdir(p):
            # A song's folder, or a folder of songs: every file of each song.
            files += [str(f) for m in expand([p]) for f in song.audio_files(m) if in_folder(str(f))]
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
        tags.stamp(out, f)

        size = os.path.getsize(out) / 1e6
        note = f"  (turned down {20 * np.log10(gain):.1f} dB so the peaks don't clip)" if gain < 1.0 else ""
        print(f"  {size:5.1f} MB  {out}{note}")
