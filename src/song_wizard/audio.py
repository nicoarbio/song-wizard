"""Audio I/O helpers. Decoding always goes through the system ffmpeg, so every
format it understands (Opus, WebM, M4A, MP3...) works everywhere."""

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

# Of a song's own files (the download, a .wav copy, an .mp3), the one shown and used first.
MAIN_FORMATS = [".opus", ".webm", ".m4a", ".flac", ".wav", ".aiff", ".aif", ".ogg", ".mp3", ".aac", ".mp4", ".mkv"]
AUDIO_EXTS = {".opus", ".webm", ".wav", ".flac", ".mp3", ".m4a", ".ogg", ".aac", ".mkv", ".mp4", ".aiff", ".aif"}

# Files this tool writes: "Title (drums).wav", "Title (no drums).wav", "Title (other).wav",
# "Title (+2).wav", "Title (80%).wav", "Title (80%, -2).wav" and "Title (click 120 BPM 4-4).wav",
# takes recorded in REAPER ("Title (record 2026-11-01 19-05-12).wav"),
# plus click tracks not made for a song ("Click 120 BPM 4-4.wav"). "(click)" and "(count-in)" files
# from an earlier, experimental click command are skipped too.
GENERATED = re.compile(r" \(((no )?(vocals|drums|bass|guitar|piano)|other|kick|snare|toms|hihat|ride|crash|drums rest|[+-]\d+(\.\d+)?|\d+(\.\d+)?%(, [+-]\d+(\.\d+)?)?|click( \d+(\.\d+)? BPM \d+-\d+( x\d+)?)?)\)( \(count-in\))?$"
                       r"| \(count-in\)$"
                       # Takes recorded in REAPER: "Title (record 2026-11-01 19-05-12).wav" (and "-001"... when
                       # several tracks record at once).
                       r"| \(record \d{4}-\d\d-\d\d \d\d-\d\d-\d\d\)(-\d+)?$"
                       r"|^Click \d+(\.\d+)? BPM \d+-\d+( x\d+)?$")


def base_of(name):
    """The song a file belongs to: 'Title (drums) (80%).wav' -> 'Title'; 'Title.mp3' -> 'Title'."""
    stem = os.path.splitext(name)[0]
    while (match := GENERATED.search(stem)) and match.start() > 0:
        stem = stem[:match.start()]
    return stem


def die(msg):
    from . import log

    log.error("%s", msg)
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
    """Write (channels, samples) float audio. A .wav is 32-bit float (peaks above 0 dB are kept);
    .mp3 and .opus are encoded by ffmpeg (lossy, a fraction of the size: right for practice)."""
    ext = os.path.splitext(os.fspath(path))[1].lower()
    if ext in LOSSY:
        require_ffmpeg()
        data = np.ascontiguousarray(audio.T, dtype="<f4").tobytes()
        cmd = ["ffmpeg", "-nostdin", "-v", "error", "-y", "-f", "f32le", "-ar", str(sr),
               "-ac", str(audio.shape[0]), "-i", "pipe:0", *LOSSY[ext], os.fspath(path)]
        subprocess.run(cmd, input=data, check=True)
        return
    sf.write(path, audio.T, sr, subtype="FLOAT")


# Stems and versions this tool writes: WAV unless [audio] stems = "mp3" or "opus" in the settings.
# WAV because Practice plays one <audio> per track and the browser jumps to the exact sample only
# in WAV: in an MP3 it guesses the spot from the bitrate, each track lands somewhere else and they
# drift apart (0.39.0 to 0.39.2 made MP3 by default). MP3/Opus are a fraction of the size.
LOSSY = {
    ".mp3": ["-c:a", "libmp3lame", "-q:a", "2", "-id3v2_version", "3"],
    ".opus": ["-c:a", "libopus", "-b:a", "160k"],
}
STEM_FORMATS = ("wav", "mp3", "opus")


def stem_ext():
    """The extension stems and versions are written with: ".wav" (default), ".mp3" or ".opus"."""
    from . import config

    value = str(config.get("audio", "stems")).strip().lower().lstrip(".")
    return f".{value}" if value in STEM_FORMATS else ".wav"


def output_path(src, suffix):
    """'dir/Title.opus' + 'drums' -> 'dir/Title (drums).wav' (or .mp3/.opus, per the settings)"""
    return f"{os.path.splitext(src)[0]} ({suffix}){stem_ext()}"


def stem_path(song, part):
    """The song's file for one part ("Title (bass)"), as a Path: the format the settings choose
    first, then the others (songs made before the change have .wav, others .opus). None if there isn't one."""
    song = Path(song)
    base = base_of(song.name)
    for ext in dict.fromkeys([stem_ext(), ".mp3", ".opus", ".wav"]):
        stem = song.with_name(f"{base} ({part}){ext}")
        if stem.is_file():
            return stem
    return None


class Progress:
    """A line rewritten in place with \\r: "  45%  (2/5) Title.opus". The interface turns the
    percentage into a progress bar. clear() before printing anything else."""

    def __init__(self, total):
        self.total = total
        self.width = 0
        self.shown = None

    def update(self, index, fraction, name):
        percent = int(100 * (index + min(max(fraction, 0), 1)) / self.total)
        text = f"  {percent:3d}%  " + (f"({index + 1}/{self.total}) " if self.total > 1 else "") + name
        if text == self.shown:
            return
        self.shown = text
        print("\r" + text.ljust(self.width), end="", flush=True)
        self.width = max(self.width, len(text))

    def clear(self):
        if self.width:
            print("\r" + " " * self.width + "\r", end="", flush=True)
        self.width, self.shown = 0, None
