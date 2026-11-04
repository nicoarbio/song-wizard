// Graba unos instantes de la entrada para medir la demora (ida y vuelta: salida → mic).
class Rec extends AudioWorkletProcessor {
  constructor() {
    super();
    this.left = 0;
    this.port.onmessage = (e) => {
      this.left = Math.round(e.data.seconds * sampleRate);
      this.parts = [];
      this.start = null;
    };
  }

  process(inputs) {
    const ch = inputs[0] && inputs[0][0];
    if (this.left > 0 && ch) {
      if (this.start === null) this.start = currentTime;
      this.parts.push(ch.slice());
      this.left -= ch.length;
      if (this.left <= 0) {
        const data = new Float32Array(this.parts.reduce((n, p) => n + p.length, 0));
        let at = 0;
        for (const p of this.parts) { data.set(p, at); at += p.length; }
        this.port.postMessage({ start: this.start, data }, [data.buffer]);
        this.parts = [];
      }
    }
    return true;
  }
}
registerProcessor("rec", Rec);
