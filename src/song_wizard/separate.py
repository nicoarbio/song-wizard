"""Stem separation with the UVR model zoo (via audio-separator).

Each instrument uses the model that separates it best. "Rest" is the original mix minus
the instrument, so instrument + rest always add back up to the exact original.
"""

import logging
import os
import tempfile
from collections import defaultdict

import numpy as np
import soundfile as sf

from .audio import expand, load, output_path, save
from .paths import MODELS_DIR

# instrument -> (model file, stem name the model gives it)
MODELS = {
    "vocals": ("vocals_mel_band_roformer.ckpt", "vocals"),
    "drums": ("htdemucs_ft.yaml", "drums"),
    "bass": ("htdemucs_ft.yaml", "bass"),
    "guitar": ("htdemucs_6s.yaml", "guitar"),
}
STEMS = list(MODELS)

# The models work at 44.1 kHz, so outputs are 44.1 kHz too.
SR = 44100
# Input is scaled to this peak before separating and scaled back afterwards (exact in float).
# audio-separator rescales any stem peaking above 1.0, which would break the subtraction;
# with this much headroom no stem gets there.
HEADROOM = 0.5


def run(stems, paths):
    from audio_separator.separator import Separator

    files = list(expand(paths, skip_generated=True))
    if not files:
        return

    by_model = defaultdict(list)
    for stem in dict.fromkeys(stems):
        model, name = MODELS[stem]
        by_model[model].append((stem, name))

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="song-wizard-") as tmp:
        # Decode every song once: 44.1 kHz stereo float, scaled to leave headroom.
        mixes = {}
        for i, f in enumerate(files):
            audio, _ = load(f, sr=SR)
            peak = float(np.abs(audio).max()) or 1.0
            scale = min(1.0, HEADROOM / peak)
            path = os.path.join(tmp, f"in{i}.wav")
            save(path, audio * scale, SR)
            mixes[f] = (audio, scale, path)

        # Outer loop over models so each model is loaded only once.
        for model, wanted in by_model.items():
            print(f"Model {model} ({', '.join(s for s, _ in wanted)})")
            sep = Separator(
                log_level=logging.ERROR,
                model_file_dir=str(MODELS_DIR),
                output_dir=tmp,
                output_format="WAV",
                use_soundfile=True,
                normalization_threshold=1.0,
                amplification_threshold=0,
                output_single_stem=wanted[0][1] if len(wanted) == 1 else None,
                sample_rate=SR,
            )
            sep.load_model(model_filename=model)
            for f, (audio, scale, path) in mixes.items():
                names = {name: f"out-{name}" for _, name in wanted}
                sep.separate(path, custom_output_names=names)
                for stem, name in wanted:
                    part, _ = sf.read(os.path.join(tmp, f"out-{name}.wav"), dtype="float32", always_2d=True)
                    part = fit(part.T / scale, audio.shape[1])
                    save(output_path(f, stem), part, SR)
                    save(output_path(f, f"no {stem}"), audio - part, SR)
                    print(f"  {stem:<6}  {output_path(f, stem)}")


def fit(audio, length):
    """Trim or zero-pad (channels, samples) to an exact length."""
    if audio.shape[1] >= length:
        return audio[:, :length]
    return np.pad(audio, ((0, 0), (0, length - audio.shape[1])))
