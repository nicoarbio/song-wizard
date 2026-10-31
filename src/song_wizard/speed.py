"""Speed changes without changing pitch (optionally with a pitch shift too), with Rubber Band."""

from .audio import die
from .transpose import stretch

MIN, MAX = 25, 200


def run(percent, paths, semitones=0):
    if not MIN <= percent <= MAX:
        die(f"The speed must be between {MIN}% and {MAX}%.")
    options = ["-T", f"{percent / 100:.6g}"]
    label = f"{percent:g}%"
    if semitones:
        options += ["-p", str(semitones)]
        label += f", {semitones:+g}"
    stretch(paths, options, label)
