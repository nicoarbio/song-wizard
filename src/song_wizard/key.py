"""Key detection with Essentia: four key profiles vote."""

import collections
import os
import subprocess

from . import results
from .audio import expand, load

PROFILES = ["krumhansl", "edma", "bgate", "shaath"]
NOTES = ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]
MINOR_NOTES = ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "G#", "A", "Bb", "B"]


def short(key, scale):
    return key + ("m" if scale == "minor" else "")


def relative(key, scale):
    i = NOTES.index(key) if key in NOTES else MINOR_NOTES.index(key)
    if scale == "minor":
        return short(NOTES[(i + 3) % 12], "major")
    return short(MINOR_NOTES[(i - 3) % 12], "minor")


def run(paths):
    import essentia
    essentia.log.infoActive = False
    essentia.log.warningActive = False
    import essentia.standard as es

    found = []
    for f in expand(paths, skip_generated=True):
        try:
            audio, _ = load(f, sr=44100, mono=True)
        except subprocess.CalledProcessError:
            print(f"  ??{'':34}{os.path.basename(f)}  (could not read)")
            continue
        votes, strength = collections.Counter(), collections.Counter()
        for p in PROFILES:
            k, s, st = es.KeyExtractor(profileType=p)(audio[0])
            votes[k, s] += 1
            strength[k, s] += st
        # Most votes wins; ties are broken by the summed strength of each profile.
        key, scale = max(votes, key=lambda k: (votes[k], strength[k]))
        n = votes.pop((key, scale))
        rel = f"relative {relative(key, scale)}"
        doubt = ""
        if votes:
            doubt = "  uncertain, also: " + ", ".join(short(*k) for k, _ in votes.most_common())
        result = f"{short(key, scale):<4} {key + ' ' + scale:<9} {rel:<14} {n}/{len(PROFILES)}"
        print(f"  {result}  {os.path.basename(f)}{doubt}")
        found.append((f, result + doubt))
    for out in results.save("key", found):
        print(f"Saved to {out}")
