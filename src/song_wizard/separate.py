"""Stem separation with the UVR model zoo (via audio-separator).

Each instrument uses the model that separates it best. "Rest" is the original mix minus
the instrument, so instrument + rest always add back up to the exact original. With "all",
"other" is the original minus the four instruments, so all five stems add back up to it too.
Piano isn't part of "all": only worth it in songs with a real piano (synths stay in "other"),
and its model is a big download. "drumkit" splits the drums stem (separated first if missing)
into kick, snare, toms, hi-hat, ride and crash, plus the rest of the drums.
"""

import logging
import os
import tempfile
from collections import defaultdict

import numpy as np
import soundfile as sf

from . import log, tags
from .audio import expand, load, output_path, save
from .device import pick
from .paths import MODELS_DIR

# instrument -> (model file, stem name the model gives it)
MODELS = {
    "vocals": ("vocals_mel_band_roformer.ckpt", "vocals"),
    "drums": ("htdemucs_ft.yaml", "drums"),
    "bass": ("htdemucs_ft.yaml", "bass"),
    # BS-Roformer SW (6 stems): a cleaner guitar than Demucs 6s (which picked up winds and
    # piano too, by ear), and a piano; both come out of one pass.
    "guitar": ("BS-Roformer-SW.ckpt", "guitar"),
    "piano": ("BS-Roformer-SW.ckpt", "piano"),
}
# The drum kit, split from the drums stem by MDX23C DrumSep: each piece, plus what's left of the
# drums, so they add back up to them exactly. (our name, the model's name for it)
DRUMKIT = "drumkit"
KIT_MODEL = "MDX23C-DrumSep-aufr33-jarredou.ckpt"
KIT_PARTS = [("kick", "kick"), ("snare", "snare"), ("toms", "toms"), ("hihat", "hh"), ("ride", "ride"), ("crash", "crash")]
KIT_REST = "drums rest"
STEMS = [*MODELS, DRUMKIT]
# What "all" separates (plus "other", the rest).
EVERY = ["vocals", "drums", "bass", "guitar"]
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
    log.info("separating on %s", desc)
    if warning:
        print(f"Warning: {warning}")
        log.info("warning: %s", warning)

    kit = DRUMKIT in stems
    stems, every = choose([s for s in stems if s != DRUMKIT])

    by_model = defaultdict(list)
    for stem in stems:
        model, name = MODELS[stem]
        by_model[model].append((stem, name))

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="song-wizard-") as tmp:
        # Decode every song once to 44.1 kHz stereo float, scaled to leave headroom. Only the
        # temp files are kept, not the audio, so a big folder doesn't fill up the RAM.
        mixes = [(f, *headroom(load(f, sr=SR)[0], os.path.join(tmp, f"in{i}.wav"))) for i, f in enumerate(files)]

        def keep(f, mix, parts):
            for stem, part in parts.items():
                save(output_path(f, stem), part, SR)
                tags.stamp(output_path(f, stem), f)
                # With "all", muting a track does what "no X" would; piano isn't in "all".
                if not every or stem not in EVERY:
                    save(output_path(f, f"no {stem}"), mix - part, SR)
                    tags.stamp(output_path(f, f"no {stem}"), f)
                print(f"  {stem:<6}  {output_path(f, stem)}")

        # Outer loop over models so each model is loaded only once.
        for model, wanted in by_model.items():
            device = separate_with(model, wanted, mixes, device, tmp, keep)
        # The drum kit is split from the drums alone: songs without them get them first.
        if kit and "drums" not in stems:
            missing = [m for m in mixes if not os.path.exists(output_path(m[0], "drums"))]
            if missing:
                device = separate_with(MODELS["drums"][0], [("drums", MODELS["drums"][1])], missing, device, tmp, keep)

        if every:
            for f, scale, path in mixes:
                mix, _ = sf.read(path, dtype="float32", always_2d=True)
                other = mix.T / scale
                for stem in EVERY:
                    part, _ = load(output_path(f, stem), sr=SR)  # as stored: Opus is lossy, 48 kHz
                    other -= part.T
                save(output_path(f, "other"), other, SR)
                tags.stamp(output_path(f, "other"), f)
                print(f"  {'other':<6}  {output_path(f, 'other')}")

        if kit:
            drums = [(f, *headroom(load(output_path(f, "drums"), sr=SR)[0], os.path.join(tmp, f"kit{i}.wav")))
                     for i, (f, _, _) in enumerate(mixes)]

            def keep_kit(f, mix, parts):
                # Parts + rest add back up to the exact drums, like every stem here.
                for stem, part in parts.items():
                    save(output_path(f, stem), part, SR)
                    tags.stamp(output_path(f, stem), f)
                    print(f"  {stem:<6}  {output_path(f, stem)}")
                save(output_path(f, KIT_REST), mix - sum(parts.values()), SR)
                tags.stamp(output_path(f, KIT_REST), f)
                print(f"  {'rest':<6}  {output_path(f, KIT_REST)}")
            separate_with(KIT_MODEL, KIT_PARTS, drums, device, tmp, keep_kit)


def headroom(audio, path):
    """Write audio to path scaled to leave headroom; (scale, path)."""
    peak = float(np.abs(audio).max()) or 1.0
    scale = min(1.0, HEADROOM / peak)
    save(path, audio * scale, SR)
    return scale, path


def separate_with(model, wanted, inputs, device, tmp, keep):
    """Run one model over inputs [(song, scale, wav path)], calling keep(song, mix, {stem: part})
    for each, at their original level. Returns the device (the CPU once the GPU ran out of
    memory)."""
    print(f"Model {model} ({', '.join(s for s, _ in wanted)})")
    sep = separator(model, wanted, device, tmp)
    names = {name: f"out-{name}" for _, name in wanted}
    for f, scale, path in inputs:
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
        parts = {}
        for stem, name in wanted:
            part, _ = sf.read(os.path.join(tmp, f"out-{name}.wav"), dtype="float32", always_2d=True)
            parts[stem] = fit(part.T / scale, mix.shape[1])
        keep(f, mix, parts)
    return device


def choose(stems):
    """The instruments to separate, in order, and whether "all" was asked for (then the "no X"
    files of its instruments would be redundant: muting a track gives the same)."""
    every = ALL in stems
    if every:
        return [*EVERY, *(s for s in dict.fromkeys(stems) if s != ALL and s not in EVERY)], True
    return list(dict.fromkeys(stems)), False


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
