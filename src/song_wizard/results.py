"""A song's key and tempo, as one line of text each in its folder: "key.txt" and "tempo.txt".

The tempo is one for the song, whoever set it:
  "120.0 BPM  steady"                         detected by song-wizard bpm
  "120.25 BPM 4/4, first beat 0.512 s"        where the beats fall (song-wizard align): the click
  "120.25 BPM 4/4, first beat 0.512 s  set by hand"   adjusted in the practice player, or typed in

Detecting again never replaces what was set by hand, and song-wizard bpm doesn't replace where the
beats fall (it only knows the tempo), unless forced.
"""

import os

from . import song

# Results typed in by hand end with this; detecting again leaves them alone unless forced.
HAND = "set by hand"
WHAT = ("key", "tempo")


def read(path, what):
    """The song's key or tempo as saved, or None."""
    try:
        text = song.data(path, what).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    lines = [l.strip() for l in text.splitlines() if l.strip() and not l.startswith("#")]
    return lines[0] if lines else None


def save(path, what, text):
    """Save it; returns the file written."""
    out = song.data(path, what)
    tmp = out.with_name(out.name + ".tmp")
    tmp.write_text(text.strip() + "\n", encoding="utf-8")
    os.replace(tmp, out)
    return out


def by_hand(path, what):
    """The result saved if it was set by hand, else None."""
    text = read(path, what)
    return text if text and text.endswith(HAND) else None


def hand(text):
    return f"{text}  {HAND}"
