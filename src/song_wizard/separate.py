"""Stem separation with the UVR model zoo (via audio-separator).

Each instrument uses the model that separates it best. "Rest" is the original mix minus
the instrument, so instrument + rest always add back up to the exact original. With "all",
"other" is the original minus the four instruments, so all five stems add back up to it too.
"""

import logging
import os
import tempfile
from collections import defaultdict

import numpy as np
import soundfile as sf

from .audio import expand, load, output_path, save
from .device import pick
from .paths import MODELS_DIR

# instrument -> (model file, stem name the model gives it)
MODELS = {
    "vocals": ("vocals_mel_band_roformer.ckpt", "vocals"),
    "drums": ("htdemucs_ft.yaml", "drums"),
    "bass": ("htdemucs_ft.yaml", "bass"),
    "guitar": ("htdemucs_6s.yaml", "guitar"),
}
STEMS = list(MODELS)
ALL = "all"

# The models work at 44.1 kHz, so outputs are 44.1 kHz too.
SR = 44100
# Input is scaled to this peak before separating and scaled back afterwards (exact in float).
# audio-separator rescales any stem peaking above 1.0, which would break the subtraction;
# with this much headroom no stem gets there.
HEADROOM = 0.5


def run(stems, paths, force_cpu=False):
    files = list(expand(paths, skip_generated=True))
    if not files:
        return

    device, desc, warning = pick(force_cpu)
    print(f"Running on {desc}")
    if warning:
        print(f"Warning: {warning}")

    # With all stems, the "no X" files would be redundant: muting a track gives the same.
    every = ALL in stems
    if every:
        stems = STEMS

    by_model = defaultdict(list)
    for stem in dict.fromkeys(stems):
        model, name = MODELS[stem]
        by_model[model].append((stem, name))

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="song-wizard-") as tmp:
        # Decode every song once to 44.1 kHz stereo float, scaled to leave headroom. Only the
        # temp files are kept, not the audio, so a big folder doesn't fill up the RAM.
        mixes = {}
        for i, f in enumerate(files):
            audio, _ = load(f, sr=SR)
            peak = float(np.abs(audio).max()) or 1.0
            scale = min(1.0, HEADROOM / peak)
            path = os.path.join(tmp, f"in{i}.wav")
            save(path, audio * scale, SR)
            mixes[f] = (scale, path)

        # Outer loop over models so each model is loaded only once.
        for model, wanted in by_model.items():
            print(f"Model {model} ({', '.join(s for s, _ in wanted)})")
            sep = separator(model, wanted, device, tmp)
            names = {name: f"out-{name}" for _, name in wanted}
            for f, (scale, path) in mixes.items():
                try:
                    sep.separate(path, custom_output_names=names)
                except Exception as e:
                    if device == "cpu" or not out_of_memory(e):
                        raise
                    print("  the GPU ran out of memory; switching to the CPU, which is slower")
                    device = "cpu"
                    del sep
                    free_gpu_memory()
                    sep = separator(model, wanted, device, tmp)
                    sep.separate(path, custom_output_names=names)

                mix, _ = sf.read(path, dtype="float32", always_2d=True)
                mix = mix.T / scale
                for stem, name in wanted:
                    part, _ = sf.read(os.path.join(tmp, f"out-{name}.wav"), dtype="float32", always_2d=True)
                    part = fit(part.T / scale, mix.shape[1])
                    save(output_path(f, stem), part, SR)
                    if not every:
                        save(output_path(f, f"no {stem}"), mix - part, SR)
                    print(f"  {stem:<6}  {output_path(f, stem)}")

        if every:
            for f, (scale, path) in mixes.items():
                mix, _ = sf.read(path, dtype="float32", always_2d=True)
                other = mix.T / scale
                for stem in STEMS:
                    part, _ = sf.read(output_path(f, stem), dtype="float32", always_2d=True)
                    other -= part.T
                save(output_path(f, "other"), other, SR)
                print(f"  {'other':<6}  {output_path(f, 'other')}")


def separator(model, wanted, device, tmp):
    from audio_separator.separator import Separator

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
    # audio-separator picks the GPU on its own; override it when the GPU can't be used.
    if device == "cpu":
        sep.torch_device = sep.torch_device_cpu
    sep.load_model(model_filename=model)
    return sep


def out_of_memory(error):
    import torch

    # CUDA raises OutOfMemoryError; Apple's Metal backend raises a RuntimeError.
    return isinstance(error, torch.OutOfMemoryError) or "out of memory" in str(error).lower()


def free_gpu_memory():
    import gc
    import torch

    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    elif torch.backends.mps.is_available():
        torch.mps.empty_cache()


def fit(audio, length):
    """Trim or zero-pad (channels, samples) to an exact length."""
    if audio.shape[1] >= length:
        return audio[:, :length]
    return np.pad(audio, ((0, 0), (0, length - audio.shape[1])))
