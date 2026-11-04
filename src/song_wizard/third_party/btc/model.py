"""BTC's model and how it reads a song (see __init__.py for where it comes from).

The classes keep their original names and attributes, so the published weights load into them as
they are (attribute names are the keys in the weights file)."""

import math

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

# The "large vocabulary" settings (run_config.yaml with large_voca on).
SAMPLE_RATE = 22050
CHUNK_SECONDS = 10.0  # the audio features are computed 10 s at a time, as the model was trained
N_BINS, BINS_PER_OCTAVE, HOP = 144, 24, 2048
TIMESTEP = 108  # frames per window the model sees: 10 s
CONFIG = {"feature_size": 144, "hidden_size": 128, "num_layers": 8, "num_heads": 4, "total_key_depth": 128,
          "total_value_depth": 128, "filter_size": 128, "num_chords": 170}

ROOTS = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
QUALITIES = ["min", "maj", "dim", "aug", "min6", "maj6", "min7", "minmaj7", "maj7", "7", "dim7", "hdim7", "sus2", "sus4"]


def chord_name(index):
    """The model's output index as a chord label ("A:min7", "C" for C major, "N" for no chord)."""
    if index == 169:
        return "N"
    if index == 168:
        return "X"  # a chord outside its vocabulary
    root, quality = ROOTS[index // 14], QUALITIES[index % 14]
    return root if quality == "maj" else f"{root}:{quality}"


def _gen_bias_mask(max_length):
    """-Inf above the diagonal: a direction of attention that can't look the other way."""
    mask = np.triu(np.full([max_length, max_length], -np.inf), 1)
    return torch.from_numpy(mask).type(torch.FloatTensor).unsqueeze(0).unsqueeze(1)


def _gen_timing_signal(length, channels, min_timescale=1.0, max_timescale=1.0e4):
    """A [1, length, channels] signal of sinusoids that tells the model where each frame is."""
    position = np.arange(length)
    num_timescales = channels // 2
    increment = math.log(float(max_timescale) / float(min_timescale)) / (float(num_timescales) - 1)
    inv_timescales = min_timescale * np.exp(np.arange(num_timescales).astype(float) * -increment)
    scaled_time = np.expand_dims(position, 1) * np.expand_dims(inv_timescales, 0)
    signal = np.concatenate([np.sin(scaled_time), np.cos(scaled_time)], axis=1)
    signal = np.pad(signal, [[0, 0], [0, channels % 2]], "constant", constant_values=[0.0, 0.0])
    return torch.from_numpy(signal.reshape([1, length, channels])).type(torch.FloatTensor)


class LayerNorm(nn.Module):
    def __init__(self, features, eps=1e-6):
        super().__init__()
        self.gamma = nn.Parameter(torch.ones(features))
        self.beta = nn.Parameter(torch.zeros(features))
        self.eps = eps

    def forward(self, x):
        mean = x.mean(-1, keepdim=True)
        std = x.std(-1, keepdim=True)
        return self.gamma * (x - mean) / (std + self.eps) + self.beta


class SoftmaxOutputLayer(nn.Module):
    def __init__(self, hidden_size, output_size):
        super().__init__()
        self.output_size = output_size
        self.output_projection = nn.Linear(hidden_size, output_size)
        # Unused when recognizing, but part of the published weights.
        self.lstm = nn.LSTM(input_size=hidden_size, hidden_size=int(hidden_size / 2), batch_first=True, bidirectional=True)
        self.hidden_size = hidden_size

    def forward(self, hidden):
        probs = F.softmax(self.output_projection(hidden), -1)
        return torch.topk(probs, 2)[1][:, :, 0]


class MultiHeadAttention(nn.Module):
    def __init__(self, input_depth, total_key_depth, total_value_depth, output_depth, num_heads, bias_mask=None):
        super().__init__()
        self.num_heads = num_heads
        self.query_scale = (total_key_depth // num_heads) ** -0.5
        self.bias_mask = bias_mask
        self.query_linear = nn.Linear(input_depth, total_key_depth, bias=False)
        self.key_linear = nn.Linear(input_depth, total_key_depth, bias=False)
        self.value_linear = nn.Linear(input_depth, total_value_depth, bias=False)
        self.output_linear = nn.Linear(total_value_depth, output_depth, bias=False)

    def _split_heads(self, x):
        shape = x.shape
        return x.view(shape[0], shape[1], self.num_heads, shape[2] // self.num_heads).permute(0, 2, 1, 3)

    def _merge_heads(self, x):
        shape = x.shape
        return x.permute(0, 2, 1, 3).contiguous().view(shape[0], shape[2], shape[3] * self.num_heads)

    def forward(self, queries, keys, values):
        queries = self._split_heads(self.query_linear(queries)) * self.query_scale
        keys = self._split_heads(self.key_linear(keys))
        values = self._split_heads(self.value_linear(values))
        logits = torch.matmul(queries, keys.permute(0, 1, 3, 2))
        if self.bias_mask is not None:
            logits += self.bias_mask[:, :, :logits.shape[-2], :logits.shape[-1]].type_as(logits.data)
        weights = nn.functional.softmax(logits, dim=-1)
        return self.output_linear(self._merge_heads(torch.matmul(weights, values)))


class Conv(nn.Module):
    """Padding and convolution over [batch, sequence, hidden] inputs, padded on both sides."""

    def __init__(self, input_size, output_size, kernel_size):
        super().__init__()
        self.pad = nn.ConstantPad1d((kernel_size // 2, (kernel_size - 1) // 2), 0)
        self.conv = nn.Conv1d(input_size, output_size, kernel_size=kernel_size, padding=0)

    def forward(self, inputs):
        return self.conv(self.pad(inputs.permute(0, 2, 1))).permute(0, 2, 1)


class PositionwiseFeedForward(nn.Module):
    """Conv + ReLU + conv + ReLU on each frame (as in the original, the ReLU follows both)."""

    def __init__(self, input_depth, filter_size, output_depth):
        super().__init__()
        self.layers = nn.ModuleList([Conv(input_depth, filter_size, 3), Conv(filter_size, output_depth, 3)])
        self.relu = nn.ReLU()

    def forward(self, x):
        for layer in self.layers:
            x = self.relu(layer(x))
        return x


class self_attention_block(nn.Module):  # noqa: N801  (the weights' names)
    def __init__(self, hidden_size, total_key_depth, total_value_depth, filter_size, num_heads, bias_mask):
        super().__init__()
        self.multi_head_attention = MultiHeadAttention(hidden_size, total_key_depth, total_value_depth, hidden_size,
                                                       num_heads, bias_mask)
        self.positionwise_convolution = PositionwiseFeedForward(hidden_size, filter_size, hidden_size)
        self.layer_norm_mha = LayerNorm(hidden_size)
        self.layer_norm_ffn = LayerNorm(hidden_size)

    def forward(self, x):
        x_norm = self.layer_norm_mha(x)
        x = x + self.multi_head_attention(x_norm, x_norm, x_norm)
        return x + self.positionwise_convolution(self.layer_norm_ffn(x))


class bi_directional_self_attention(nn.Module):  # noqa: N801
    def __init__(self, hidden_size, total_key_depth, total_value_depth, filter_size, num_heads, max_length):
        super().__init__()
        forward = _gen_bias_mask(max_length)
        self.attn_block = self_attention_block(hidden_size, total_key_depth, total_value_depth, filter_size, num_heads,
                                               forward)
        self.backward_attn_block = self_attention_block(hidden_size, total_key_depth, total_value_depth, filter_size,
                                                        num_heads, torch.transpose(forward, dim0=2, dim1=3))
        self.linear = nn.Linear(hidden_size * 2, hidden_size)

    def forward(self, x):
        return self.linear(torch.cat((self.attn_block(x), self.backward_attn_block(x)), dim=2))


class bi_directional_self_attention_layers(nn.Module):  # noqa: N801
    def __init__(self, embedding_size, hidden_size, num_layers, num_heads, total_key_depth, total_value_depth,
                 filter_size, max_length):
        super().__init__()
        self.timing_signal = _gen_timing_signal(max_length, hidden_size)
        self.embedding_proj = nn.Linear(embedding_size, hidden_size, bias=False)
        self.self_attn_layers = nn.Sequential(*[
            bi_directional_self_attention(hidden_size, total_key_depth, total_value_depth, filter_size, num_heads,
                                          max_length) for _ in range(num_layers)])
        self.layer_norm = LayerNorm(hidden_size)

    def forward(self, inputs):
        x = self.embedding_proj(inputs)
        x += self.timing_signal[:, :inputs.shape[1], :].type_as(inputs.data)
        return self.layer_norm(self.self_attn_layers(x))


class BTC_model(nn.Module):  # noqa: N801
    def __init__(self):
        super().__init__()
        c = CONFIG
        self.self_attn_layers = bi_directional_self_attention_layers(
            c["feature_size"], c["hidden_size"], c["num_layers"], c["num_heads"], c["total_key_depth"],
            c["total_value_depth"], c["filter_size"], TIMESTEP)
        self.output_layer = SoftmaxOutputLayer(c["hidden_size"], c["num_chords"])


def features(audio):
    """The model's input from mono audio at 22050 Hz: log constant-Q, 10 s at a time; and the
    seconds per frame."""
    import librosa

    chunk = int(SAMPLE_RATE * CHUNK_SECONDS)
    parts, start = [], 0
    while len(audio) > start + chunk:
        parts.append(librosa.cqt(audio[start:start + chunk], sr=SAMPLE_RATE, n_bins=N_BINS,
                                 bins_per_octave=BINS_PER_OCTAVE, hop_length=HOP))
        start += chunk
    parts.append(librosa.cqt(audio[start:], sr=SAMPLE_RATE, n_bins=N_BINS, bins_per_octave=BINS_PER_OCTAVE,
                             hop_length=HOP))
    return np.log(np.abs(np.concatenate(parts, axis=1)) + 1e-6), CHUNK_SECONDS / TIMESTEP


def chords(model, mean, std, audio, device="cpu"):
    """[(start, end, label)] for the whole song: the model's chord frame by frame, joined."""
    feature, per_frame = features(audio)
    feature = (feature.T - mean) / std
    frames = feature.shape[0]
    pad = (TIMESTEP - frames % TIMESTEP) % TIMESTEP
    feature = np.pad(feature, ((0, pad), (0, 0)), mode="constant", constant_values=0)
    x = torch.tensor(feature, dtype=torch.float32).unsqueeze(0).to(device)
    found = []
    with torch.no_grad():
        model.eval()
        for t in range(feature.shape[0] // TIMESTEP):
            window = x[:, TIMESTEP * t:TIMESTEP * (t + 1), :]
            found.extend(model.output_layer(model.self_attn_layers(window)).squeeze(0).tolist())
    found = found[:frames]
    out, start = [], 0
    for i in range(1, len(found) + 1):
        if i == len(found) or found[i] != found[start]:
            out.append((round(start * per_frame, 3), round(i * per_frame, 3), chord_name(found[start])))
            start = i
    return out
