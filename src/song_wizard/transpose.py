"""Pitch shifting with the Rubber Band command-line tool (R3 engine). Length and timing are kept.

The CLI is used instead of a Python binding because it processes the whole file at once,
which keeps transients within ~1 ms of their original position (the bindings drift by tens
of ms, enough to be heard against a click).
"""

import os
import shutil
import subprocess
import tempfile

import soundfile as sf

from .audio import die, expand, load, output_path, save

# rubberband clips everything above 0 dB, even in float. Scaling by a power of two before
# and after is exact in float, so peaks above 0 dB survive intact.
SCALE = 0.25


def run(semitones, paths):
    if not shutil.which("rubberband"):
        die('rubberband is missing. Run "song-wizard setup" to see how to install it.')

    label = f"{semitones:+g}"
    with tempfile.TemporaryDirectory(prefix="song-wizard-") as tmp:
        src, dst = os.path.join(tmp, "in.wav"), os.path.join(tmp, "out.wav")
        for f in expand(paths):
            audio, sr = load(f)
            save(src, audio * SCALE, sr)
            result = subprocess.run(["rubberband", "--fine", "-q", "-p", str(semitones), src, dst],
                                    capture_output=True, text=True)
            if result.returncode != 0:
                die(result.stderr.strip() or result.stdout.strip())
            shifted, _ = sf.read(dst, dtype="float32", always_2d=True)
            out = output_path(f, label)
            save(out, shifted.T / SCALE, sr)
            print(f"  {label}  {out}")
