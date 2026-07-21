export class AudioAnalyzer {
    constructor() {
        this.context = new (window.AudioContext || window.webkitAudioContext)();
        this.analyzer = this.context.createAnalyser();
        this.analyzer.fftSize = 256;
        this.dataArray = new Uint8Array(this.analyzer.frequencyBinCount);
        this.volume = 0;
    }

    async init() {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        const source = this.context.createMediaStreamSource(stream);
        source.connect(this.analyzer);
    }

    update() {
        this.analyzer.getByteFrequencyData(this.dataArray);
        let sum = 0;
        for (let i = 0; i < this.dataArray.length; i++) {
            sum += this.dataArray[i];
        }
        this.volume = sum / this.dataArray.length / 255;
        return this.volume;
    }
}