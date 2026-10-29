// frontend/voz-worklet.js — captura do microfone em PCM16 16 kHz mono
class CapturaPCM extends AudioWorkletProcessor {
    constructor() {
        super();
        this.passo = sampleRate / 16000;   // sampleRate é global do worklet
        this.fase = 0;
        this.acc = 0;
        this.cnt = 0;
        this.saida = new Int16Array(1600); // 100 ms
        this.n = 0;
    }

    process(inputs) {
        const canal = inputs[0] && inputs[0][0];

        if (!canal) {
            return true;
        }

        for (let i = 0; i < canal.length; i++) {
            this.acc += canal[i];
            this.cnt++;
            this.fase++;

            if (this.fase >= this.passo) {
                this.fase -= this.passo;

                const v = Math.max(-1, Math.min(1, this.acc / this.cnt));
                this.saida[this.n++] = v < 0 ? v * 32768 : v * 32767;
                this.acc = 0;
                this.cnt = 0;

                if (this.n === this.saida.length) {
                    this.port.postMessage(this.saida.buffer, [this.saida.buffer]);
                    this.saida = new Int16Array(1600);
                    this.n = 0;
                }
            }
        }

        return true;
    }
}

registerProcessor("captura-pcm", CapturaPCM);