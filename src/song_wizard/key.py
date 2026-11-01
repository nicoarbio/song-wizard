"""Key detection with Essentia: four key profiles vote."""

import collections
import os
import re
import subprocess

from . import results
from .audio import die, expand, load

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


# "Am", "C#", "Bb minor", "F# major", and in Spanish "La menor", "Sib", "Fa#m".
TYPED = re.compile(r"(?P<note>do|re|mi|fa|sol|la|si|[a-g])\s*(?P<acc>[#♯b♭]?)\s*"
                   r"(?P<scale>m|min|minor|menor|maj|major|mayor)?", re.IGNORECASE)
SEMITONE = {"c": 0, "d": 2, "e": 4, "f": 5, "g": 7, "a": 9, "b": 11,
            "do": 0, "re": 2, "mi": 4, "fa": 5, "sol": 7, "la": 9, "si": 11}


def parse(text):
    """A key as typed -> (note, "major"|"minor") spelled like the detection does, or None."""
    match = TYPED.fullmatch((text or "").strip())
    if not match:
        return None
    i = SEMITONE[match["note"].lower()] + {"#": 1, "♯": 1, "b": -1, "♭": -1}.get(match["acc"], 0)
    scale = "minor" if (match["scale"] or "").lower() in ("m", "min", "minor", "menor") else "major"
    return (MINOR_NOTES if scale == "minor" else NOTES)[i % 12], scale


def describe(key, scale, note):
    """The key.txt line: short name, full name, relative key, then how sure (or a note)."""
    rel = f"relative {relative(key, scale)}"
    return f"{short(key, scale):<4} {key + ' ' + scale:<9} {rel:<14} {note}"


def set_by_hand(paths, text):
    found = parse(text)
    if not found:
        die(f'"{text}" is not a key. Examples: Am, C#, "Bb major", "F# minor".')
    result = describe(*found, results.HAND)
    done = [(f, result) for f in expand(paths, skip_generated=True)]
    for f, _ in done:
        print(f"  {result}  {os.path.basename(f)}")
    for out in results.save("key", done):
        print(f"Saved to {out}")


def run(paths, value=None, force=False):
    if value is not None:
        return set_by_hand(paths, value)
    import essentia
    essentia.log.infoActive = False
    essentia.log.warningActive = False
    import essentia.standard as es

    found = []
    for f in expand(paths, skip_generated=True):
        kept = None if force else results.by_hand(f, "key")
        if kept:
            print(f"  {kept}  {os.path.basename(f)}  (kept; --force detects it again)")
            continue
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
        doubt = ""
        if votes:
            doubt = "  uncertain, also: " + ", ".join(short(*k) for k, _ in votes.most_common())
        result = describe(key, scale, f"{n}/{len(PROFILES)}")
        print(f"  {result}  {os.path.basename(f)}{doubt}")
        found.append((f, result + doubt))
    for out in results.save("key", found):
        print(f"Saved to {out}")
