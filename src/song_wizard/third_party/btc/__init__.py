"""BTC, a bi-directional transformer for chord recognition (Park et al., ISMIR 2019), copied here
from https://github.com/jayg996/BTC-ISMIR19 at commit 2682317be668032e6e4b269ded36adaa2ad57df0
(MIT license, in LICENSE next to this file). Only what's needed to recognize chords is kept: the
model, the audio features it reads and its chord names; training, the CRF and the baselines are
left out. The changes: the model's settings written in (the "large vocabulary" ones, 170 chords),
the training-only code paths removed, and `chords()` added, which runs it over a whole song.
The model's weights aren't here: song_wizard.chords downloads them and checks their SHA-256."""
