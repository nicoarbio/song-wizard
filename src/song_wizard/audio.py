"""Audio I/O helpers. Decoding always goes through the system ffmpeg, so every
format it understands (Opus, WebM, M4A, MP3...) works everywhere."""

import os
import shutil
import subprocess
import sys

import numpy as np
import soundfile as sf

# Of a song's own files (the download, a .wav copy, an .mp3), the one shown and used first.
MAIN_FORMATS = [".opus", ".webm", ".m4a", ".flac", ".wav", ".aiff", ".aif", ".ogg", ".mp3", ".aac", ".mp4", ".mkv"]
AUDIO_EXTS = {".opus", ".webm", ".wav", ".flac", ".mp3", ".m4a", ".ogg", ".aac", ".mkv", ".mp4", ".aiff", ".aif"}

def die(msg):
    from . import log

    log.error("%s", msg)
    print(msg, file=sys.stderr)
    sys.exit(1)


def require_ffmpeg():
    if not shutil.which("ffmpeg"):
        die('ffmpeg is missing. Run "song-wizard setup" to see how to install it.')


def expand(paths, skip_generated=False):
    """The files named, as paths (str): a song's folder or a folder of songs gives their songs'
    main files; a file named on purpose stays itself (a stem, say), unless skip_generated, which
    takes its song instead. Exits on a folder in the layout before 0.42.0."""
    from . import song

    return [str(p) for p in (song.expand(paths) if skip_generated else song.files(paths))]


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


# Stems and versions this tool writes: Opus unless [audio] stems = "wav" or "mp3" in the settings.
# Practice plays one <audio> per track, so the format must let the browser jump to the exact spot:
# Opus does (measured in Edge: within 1-4 ms of WAV) at a twentieth of the size, and keeps peaks
# above 0 dB like the 32-bit float WAV. In an MP3 the browser guesses the spot from the bitrate,
# each track lands somewhere else and they drift apart (0.39.0 to 0.39.2 made MP3 by default).
LOSSY = {
    ".mp3": ["-c:a", "libmp3lame", "-q:a", "2", "-id3v2_version", "3"],
    ".opus": ["-c:a", "libopus", "-b:a", "160k"],
}
STEM_FORMATS = ("opus", "wav", "mp3")


def stem_ext():
    """The extension stems and versions are written with: ".opus" (default), ".wav" or ".mp3"."""
    from . import config

    value = str(config.get("audio", "stems")).strip().lower().lstrip(".")
    return f".{value}" if value in STEM_FORMATS else ".opus"


def output_path(src, suffix):
    """Where a file made from src goes, in its song's folder: the song + "drums" -> "drums.opus";
    "drums.opus" + "80%" -> "drums 80%.opus" (or .wav/.mp3, per the settings)."""
    from . import song

    return str(song.made(src, suffix))


def stem_path(path, part):
    """The song's file for one part ("bass.opus"), as a Path, or None if there isn't one."""
    from . import song

    return song.stem(path, part)


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
