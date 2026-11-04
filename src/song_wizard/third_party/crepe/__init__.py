"""CREPE, a pitch tracker (Kim et al., ICASSP 2018), in its PyTorch version torchcrepe by Max Morrison,
copied here from https://github.com/maxrmorrison/torchcrepe (version 0.0.24, commit 19e2ec3; MIT
license, in LICENSE next to this file). Only what's needed to follow a voice's pitch is kept: the
"full" model, cutting the audio into its frames, Viterbi decoding and its confidence. The changes:
the audio arrives already at 16 kHz (ffmpeg resamples it), the bins become frequencies without the
random dither (so the same song always gives the same notes), the training, embedding, file and
loudness helpers are left out, and `pitch()` runs it over a whole recording.
The model's weights aren't here: song_wizard.notes downloads them and checks their SHA-256."""
