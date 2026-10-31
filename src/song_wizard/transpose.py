"""Pitch shifting with the Rubber Band command-line tool (R3 engine). Length and timing are kept.

The CLI is used instead of a Python binding because it processes the whole file at once,
which keeps transients within ~1 ms of their original position (the bindings drift by tens
of ms, enough to be heard against a click).
"""

import os
import re
import shutil
import subprocess
import tempfile

import soundfile as sf

from .audio import Progress, die, expand, load, output_path, save

# rubberband clips everything above 0 dB, even in float. Scaling by a power of two before
# and after is exact in float, so peaks above 0 dB survive intact.
SCALE = 0.25


def run(semitones, paths):
    stretch(paths, ["-p", str(semitones)], f"{semitones:+g}")


def stretch(paths, options, label):
    """Run each file through rubberband with these options; writes "Title (label).wav"."""
    if not shutil.which("rubberband"):
        die('rubberband is missing. Run "song-wizard setup" to see how to install it.')

    files = list(expand(paths))
    progress = Progress(len(files))
    with tempfile.TemporaryDirectory(prefix="song-wizard-") as tmp:
        src, dst = os.path.join(tmp, "in.wav"), os.path.join(tmp, "out.wav")
        for i, f in enumerate(files):
            name = os.path.basename(f)
            progress.update(i, 0, name)
            try:
                audio, sr = load(f)
            except subprocess.CalledProcessError:
                progress.clear()
                print(f"  skipping {name}: could not read it")
                continue
            save(src, audio * SCALE, sr)
            # Decoding ~5%, rubberband's first pass (studying the audio) ~5%, its second ~85%.
            ok, output = rubberband(options, src, dst, lambda done: progress.update(i, 0.05 + 0.9 * done, name))
            if not ok:
                progress.clear()
                die(output)
            shifted, _ = sf.read(dst, dtype="float32", always_2d=True)
            out = output_path(f, label)
            save(out, shifted.T / SCALE, sr)
            progress.clear()
            print(f"  {label}  {out}")


def rubberband(options, src, dst, report):
    """Run rubberband, calling report(0..1) as it goes. Returns (succeeded, its output)."""
    process = subprocess.Popen(["rubberband", "--fine", *options, src, dst],
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    output, passes = b"", 0
    while chunk := process.stdout.read1(4096):
        output += chunk
        for match in re.finditer(rb"Pass (\d)|(\d+)%", chunk):
            if match.group(1):
                passes = int(match.group(1))
            else:
                percent = int(match.group(2)) / 100
                report(0.05 * percent if passes == 1 else 0.05 + 0.95 * percent)
    ok = process.wait() == 0
    # Without the progress counters, what's left is what rubberband had to say.
    text = re.sub(r"\s*\d+%\s*", " ", output.decode(errors="replace").replace("\r", " ")).strip()
    return ok, text
