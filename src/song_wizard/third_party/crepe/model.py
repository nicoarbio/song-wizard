"""CREPE's model and how it reads audio (see __init__.py for where it comes from).

The layers keep their original names, so the published weights load into them as they are."""

import functools

import numpy as np
import torch
import torch.nn.functional as F

SAMPLE_RATE = 16000  # Hz
WINDOW_SIZE = 1024  # samples
PITCH_BINS = 360
CENTS_PER_BIN = 20


class Crepe(torch.nn.Module):
    """The "full" model."""

    def __init__(self):
        super().__init__()
        in_channels = [1, 1024, 128, 128, 128, 256]
        out_channels = [1024, 128, 128, 128, 256, 512]
        self.in_features = 2048
        kernel_sizes = [(512, 1)] + 5 * [(64, 1)]
        strides = [(4, 1)] + 5 * [(1, 1)]
        batch_norm = functools.partial(torch.nn.BatchNorm2d, eps=0.0010000000474974513, momentum=0.0)
        for i in range(6):
            setattr(self, f"conv{i + 1}", torch.nn.Conv2d(in_channels[i], out_channels[i], kernel_sizes[i], strides[i]))
            setattr(self, f"conv{i + 1}_BN", batch_norm(num_features=out_channels[i]))
        self.classifier = torch.nn.Linear(in_features=self.in_features, out_features=PITCH_BINS)

    def forward(self, x):
        x = x[:, None, :, None]
        x = self.layer(x, self.conv1, self.conv1_BN, (0, 0, 254, 254))
        for i in range(2, 7):
            x = self.layer(x, getattr(self, f"conv{i}"), getattr(self, f"conv{i}_BN"))
        x = x.permute(0, 2, 1, 3).reshape(-1, self.in_features)
        return torch.sigmoid(self.classifier(x))

    @staticmethod
    def layer(x, conv, batch_norm, padding=(0, 0, 31, 32)):
        x = F.relu(conv(F.pad(x, padding)))
        return F.max_pool2d(batch_norm(x), (2, 1), (2, 1))


def frames(audio, hop, batch, device):
    """The model's input, a batch at a time: 1024-sample windows every `hop` samples, centered and
    scaled (audio: a 1-D float tensor at 16 kHz)."""
    total = 1 + int(audio.size(0) // hop)
    audio = F.pad(audio[None], (WINDOW_SIZE // 2, WINDOW_SIZE // 2))
    for i in range(0, total, batch):
        start, end = i * hop, min(audio.size(1), (i + batch - 1) * hop + WINDOW_SIZE)
        chunk = F.unfold(audio[:, None, None, start:end], kernel_size=(1, WINDOW_SIZE), stride=(1, hop))
        chunk = chunk.transpose(1, 2).reshape(-1, WINDOW_SIZE).to(device)
        chunk = chunk - chunk.mean(dim=1, keepdim=True)
        yield chunk / torch.clamp(chunk.std(dim=1, keepdim=True), min=1e-10)


_transition = None


def viterbi(probs):
    """The most likely path of pitch bins through (360, time) probabilities: a smooth line, as a
    voice moves, instead of jumping to the loudest bin frame by frame."""
    import librosa

    global _transition
    if _transition is None:
        xx, yy = np.meshgrid(range(PITCH_BINS), range(PITCH_BINS))
        t = np.maximum(12 - abs(xx - yy), 0)
        _transition = t / t.sum(axis=1, keepdims=True)
    return librosa.sequence.viterbi(probs, _transition).astype(np.int64)


def pitch(model, audio, fmin=50.0, fmax=1100.0, hop=160, batch=1024, device="cpu"):
    """(frequency in Hz, confidence 0-1) every `hop` samples of 16 kHz mono audio (numpy)."""
    x = torch.tensor(audio, dtype=torch.float32)
    out = []
    with torch.no_grad():
        model.eval()
        for chunk in frames(x, hop, batch, device):
            out.append(model(chunk).cpu())
    probs = torch.cat(out).T  # (360, time)
    cents = CENTS_PER_BIN * torch.arange(PITCH_BINS) + 1997.3794084376191
    freqs = 10 * 2 ** (cents / 1200)
    probs[freqs < fmin] = -float("inf")
    probs[freqs > fmax] = -float("inf")
    bins = viterbi(torch.softmax(probs, dim=0).numpy())
    confidence = probs.gather(0, torch.tensor(bins)[None]).squeeze(0).numpy()
    return freqs.numpy()[bins], confidence
