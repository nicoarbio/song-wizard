// Live pitch shifting for the practice player, as an AudioWorklet: a phase vocoder stretches the
// sound in time keeping its pitch (identity phase locking, Laroche & Dolson), and reading that back
// faster or slower brings it to its length again with the pitch moved. Every channel gets the same
// phase changes, worked out on their sum, so the stereo image stays put.
//
// The delay is the same for every pitch (LATENCY samples), so the page can delay the click as much
// and it stays on the beat. A new pitch starts over (a moment of silence).

const FFT_SIZE = 4096;
const HOP = FFT_SIZE / 8;  // analysis hop
const MAX_SEMITONES = 6;
// The delay that the lowest pitch needs (it reads the stretched sound slowest), for all of them.
const LATENCY = Math.ceil(FFT_SIZE / 2 + FFT_SIZE / 2 / Math.pow(2, -MAX_SEMITONES / 12) + 16);
const RING = 4 * FFT_SIZE;

class FFT {
  constructor(n) {
    this.n = n;
    this.rev = new Uint32Array(n);
    const bits = Math.log2(n);
    for (let i = 0; i < n; i++) {
      let r = 0;
      for (let b = 0; b < bits; b++) r |= ((i >> b) & 1) << (bits - 1 - b);
      this.rev[i] = r;
    }
    this.cos = new Float64Array(n / 2);
    this.sin = new Float64Array(n / 2);
    for (let i = 0; i < n / 2; i++) { this.cos[i] = Math.cos(2 * Math.PI * i / n); this.sin[i] = Math.sin(2 * Math.PI * i / n); }
  }

  // In place; inverse without the 1/n scale.
  run(re, im, inverse) {
    const n = this.n, rev = this.rev, sign = inverse ? 1 : -1;
    for (let i = 0; i < n; i++) {
      const j = rev[i];
      if (j > i) { let t = re[i]; re[i] = re[j]; re[j] = t; t = im[i]; im[i] = im[j]; im[j] = t; }
    }
    for (let size = 2; size <= n; size <<= 1) {
      const half = size >> 1, step = n / size;
      for (let start = 0; start < n; start += size) {
        for (let k = 0; k < half; k++) {
          const wr = this.cos[k * step], wi = sign * this.sin[k * step];
          const a = start + k, b = a + half;
          const tr = re[b] * wr - im[b] * wi, ti = re[b] * wi + im[b] * wr;
          re[b] = re[a] - tr; im[b] = im[a] - ti;
          re[a] += tr; im[a] += ti;
        }
      }
    }
  }
}

const wrap = (x) => x - 2 * Math.PI * Math.round(x / (2 * Math.PI));

class PitchShifter {
  constructor(channels) {
    const n = FFT_SIZE, bins = n / 2 + 1;
    this.channels = channels;
    this.fft = new FFT(n);
    this.window = new Float64Array(n);
    for (let i = 0; i < n; i++) this.window[i] = 0.5 - 0.5 * Math.cos(2 * Math.PI * i / n);
    const make = (size) => Array.from({ length: channels }, () => new Float64Array(size));
    this.input = make(n);          // the last FFT_SIZE samples in
    this.stretched = make(RING);   // the stretched sound, a ring indexed by absolute position
    this.re = make(n); this.im = make(n);
    this.mag = new Float64Array(bins);
    this.phase = new Float64Array(bins);
    this.lastPhase = new Float64Array(bins);
    this.outPhase = new Float64Array(bins);
    this.lastOutPhase = new Float64Array(bins);
    this.peaks = new Int32Array(bins);
    this.setSemitones(0);
  }

  setSemitones(semitones) {
    const st = Math.max(-MAX_SEMITONES, Math.min(MAX_SEMITONES, semitones));
    // Whole hops: the pitch lands within 2 cents of the exact one.
    this.synthesisHop = Math.round(HOP * Math.pow(2, st / 12));
    this.ratio = this.synthesisHop / HOP;
    this.scale = 8 * this.synthesisHop / (3 * FFT_SIZE * FFT_SIZE);
    // Where reading starts, so that a sound comes out LATENCY samples after it went in.
    this.offset = LATENCY * this.ratio - (1 - this.ratio) * FFT_SIZE / 2;
    for (const b of [...this.input, ...this.stretched]) b.fill(0);
    this.lastPhase.fill(0); this.lastOutPhase.fill(0);
    this.received = 0; this.produced = 0; this.frames = 0; this.cleared = 0;
  }

  process(inputs, outputs, length) {
    const n = FFT_SIZE;
    for (let i = 0; i < length; i++) {
      for (let c = 0; c < this.channels; c++) {
        const src = inputs[c] || inputs[0];
        const buf = this.input[c];
        buf[(this.received) % n] = src ? src[i] : 0;
      }
      this.received++;
      if (this.received >= n && (this.received - n) % HOP === 0) this.frame();
      // Read the stretched sound back at the other speed (cubic interpolation).
      const at = this.produced * this.ratio - this.offset;
      this.produced++;
      const k = Math.floor(at), f = at - k;
      for (let c = 0; c < this.channels; c++) {
        let value = 0;
        if (k >= 1) {
          const r = this.stretched[c];
          const y0 = r[(k - 1) % RING], y1 = r[k % RING], y2 = r[(k + 1) % RING], y3 = r[(k + 2) % RING];
          value = y1 + 0.5 * f * (y2 - y0 + f * (2 * y0 - 5 * y1 + 4 * y2 - y3 + f * (3 * (y1 - y2) + y3 - y0)));
        }
        outputs[c][i] = value;
      }
      // Done with what's behind the reading point (more than one sample when reading faster):
      // clear it, the ring comes around to it again.
      for (; this.cleared < k - 1; this.cleared++) {
        for (let c = 0; c < this.channels; c++) this.stretched[c][this.cleared % RING] = 0;
      }
    }
  }

  frame() {
    const n = FFT_SIZE, bins = n / 2 + 1, chans = this.channels, w = this.window;
    const start = this.received - n;  // absolute position of the window's first sample
    for (let c = 0; c < chans; c++) {
      const re = this.re[c], im = this.im[c], src = this.input[c];
      for (let i = 0; i < n; i++) { re[i] = src[(start + i) % n] * w[i]; im[i] = 0; }
      this.fft.run(re, im, false);
    }
    const mag = this.mag, phase = this.phase;
    let loudest = 0;
    for (let k = 0; k < bins; k++) {
      let r = 0, i = 0;
      for (let c = 0; c < chans; c++) { r += this.re[c][k]; i += this.im[c][k]; }
      mag[k] = Math.hypot(r, i);
      phase[k] = Math.atan2(i, r);
      if (mag[k] > loudest) loudest = mag[k];
    }
    let count = 0;
    const floor = loudest * 1e-6;
    for (let k = 2; k < bins - 2; k++) {
      const m = mag[k];
      if (m > floor && m > mag[k - 1] && m >= mag[k + 1] && m > mag[k - 2] && m >= mag[k + 2]) this.peaks[count++] = k;
    }
    if (!count) this.peaks[count++] = 1;
    const omega = 2 * Math.PI / n;
    for (let j = 0; j < count; j++) {
      const p = this.peaks[j];
      // The peak's true frequency, from how far its phase moved; its phase after a synthesis hop.
      const freq = omega * p + wrap(phase[p] - this.lastPhase[p] - omega * p * HOP) / HOP;
      const rotation = this.lastOutPhase[p] + freq * this.synthesisHop - phase[p];
      const cr = Math.cos(rotation), ci = Math.sin(rotation);
      const from = j === 0 ? 0 : Math.ceil((this.peaks[j - 1] + p) / 2);
      const to = j === count - 1 ? bins - 1 : Math.ceil((p + this.peaks[j + 1]) / 2) - 1;
      for (let k = from; k <= to; k++) {
        for (let c = 0; c < chans; c++) {
          const r = this.re[c][k], i = this.im[c][k];
          this.re[c][k] = r * cr - i * ci;
          this.im[c][k] = r * ci + i * cr;
        }
        this.outPhase[k] = wrap(phase[k] + rotation);
      }
    }
    this.lastPhase.set(phase);
    this.lastOutPhase.set(this.outPhase);

    const at = this.frames * this.synthesisHop;  // where this frame goes in the stretched sound
    this.frames++;
    for (let c = 0; c < chans; c++) {
      const re = this.re[c], im = this.im[c];
      im[0] = 0; im[n / 2] = 0;
      for (let k = 1; k < n / 2; k++) { re[n - k] = re[k]; im[n - k] = -im[k]; }
      this.fft.run(re, im, true);
      const out = this.stretched[c];
      for (let i = 0; i < n; i++) out[(at + i) % RING] += re[i] * w[i] * this.scale;
    }
  }
}

if (typeof registerProcessor === "function") {
  registerProcessor("pitch-shifter", class extends AudioWorkletProcessor {
    constructor() {
      super();
      this.shifter = new PitchShifter(2);
      this.port.onmessage = (e) => this.shifter.setSemitones(e.data.semitones);
    }
    process(inputs, outputs) {
      const out = outputs[0];
      this.shifter.process(inputs[0], out.length === 1 ? [out[0], new Float32Array(out[0].length)] : out, out[0].length);
      return true;
    }
  });
} else if (typeof module === "object") {
  module.exports = { PitchShifter, FFT_SIZE, LATENCY };
}
