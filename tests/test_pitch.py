"""Live pitch for the practice player (static/pitch.js), run with Node: right pitch, fixed delay."""

import json
import re
import shutil
import subprocess
from importlib import resources

import numpy as np
import pytest

PITCH_JS = resources.files("song_wizard") / "static" / "pitch.js"
SR = 44100

# Feeds the shifter like the browser does (blocks of 128) and prints the output as JSON.
RUN = """
const { PitchShifter } = require(process.argv[1]);
const input = JSON.parse(require("fs").readFileSync(0, "utf8"));
const sh = new PitchShifter(2);
sh.setSemitones(input.semitones);
const x = Float32Array.from(input.samples), out = new Float32Array(x.length);
for (let s = 0; s < x.length; s += 128) {
  const len = Math.min(128, x.length - s);
  sh.process([x.subarray(s, s + len), x.subarray(s, s + len)], [out.subarray(s, s + len), new Float32Array(len)], len);
}
process.stdout.write(JSON.stringify(Array.from(out)));
"""


def latency():
    return int(re.search(r"LATENCY = (\d+)", node_eval("console.log('LATENCY = ' + m.LATENCY)")).group(1))


def node_eval(code):
    return subprocess.run(["node", "-e", f"const m = require({json.dumps(str(PITCH_JS))}); {code}"],
                          capture_output=True, text=True, check=True).stdout


def shift(samples, semitones):
    out = subprocess.run(["node", "-e", RUN, str(PITCH_JS)], input=json.dumps({"semitones": semitones, "samples": samples.tolist()}),
                         capture_output=True, text=True, check=True).stdout
    return np.array(json.loads(out))


needs_node = pytest.mark.skipif(not shutil.which("node"), reason="needs Node.js")


def test_page_delays_the_click_as_much():
    page = (resources.files("song_wizard") / "ui.html").read_text()
    script = PITCH_JS.read_text()
    n = int(re.search(r"const FFT_SIZE = (\d+);", script).group(1))
    top = int(re.search(r"const MAX_SEMITONES = (\d+);", script).group(1))
    expected = int(np.ceil(n / 2 + n / 2 / 2 ** (-top / 12) + 16))
    assert int(re.search(r"const PITCH_LATENCY = (\d+);", page).group(1)) == expected
    assert f'min="-{top}" max="{top}"' in page


@needs_node
def test_latency_constant():
    assert latency() == int(re.search(r"const PITCH_LATENCY = (\d+);",
                                      (resources.files("song_wizard") / "ui.html").read_text()).group(1))


@needs_node
@pytest.mark.parametrize("semitones", [-6, -3, -1, 2, 5, 6])
def test_pitch_moves_exactly(semitones):
    t = np.arange(3 * SR) / SR
    y = shift(0.3 * np.sin(2 * np.pi * 98 * t) + 0.3 * np.sin(2 * np.pi * 440 * t), semitones)[SR:]
    spectrum = np.abs(np.fft.rfft(y * np.hanning(len(y))))
    freqs = np.fft.rfftfreq(len(y), 1 / SR)
    ratio = 2 ** (semitones / 12)
    for f in (98, 440):
        near = np.flatnonzero((freqs > f * ratio * 0.95) & (freqs < f * ratio * 1.05))
        i = near[np.argmax(spectrum[near])]
        a, b, c = np.log(spectrum[i - 1:i + 2])
        found = freqs[i] + (a - c) / (2 * (a - 2 * b + c)) * (freqs[1] - freqs[0])  # between bins
        assert abs(1200 * np.log2(found / (f * ratio))) < 3  # cents
    # Nothing else anywhere near as loud, and the same level.
    others = (np.abs(freqs - 98 * ratio) > 10) & (np.abs(freqs - 440 * ratio) > 10)
    assert spectrum[others].max() < spectrum.max() * 10 ** (-60 / 20)
    assert 0.29 < np.sqrt(np.mean(y ** 2)) < 0.31


@needs_node
@pytest.mark.parametrize("semitones", [-6, -2, 0, 3, 6])
def test_same_delay_for_every_pitch(semitones):
    x = np.zeros(SR)
    x[10000] = 1.0
    energy = shift(x, semitones) ** 2
    # An impulse gets spread by the shifting: its center lands LATENCY samples later, within 2 ms.
    center = (energy * np.arange(len(energy))).sum() / energy.sum()
    assert abs(center - 10000 - latency()) < 0.002 * SR
