import { Engine } from './gl.js';
import { AudioAnalyzer } from './audio.js';

class AmbientPlayer {
    constructor() {
        this.context = null;
        this.analyzer = null;
        this.master = null;
        this.dataArray = null;
        this.volume = 0;
        this.track = 'part01';
        this.isPlaying = false;
        this.tracks = {
            part01: new URL('./audio/nordic-01.mp3', import.meta.url).href,
            part02: new URL('./audio/nordic-02.mp3', import.meta.url).href,
            part03: new URL('./audio/nordic-03.mp3', import.meta.url).href,
            part04: new URL('./audio/nordic-04.mp3', import.meta.url).href,
            part05: new URL('./audio/nordic-05.mp3', import.meta.url).href,
            part06: new URL('./audio/nordic-06.mp3', import.meta.url).href,
            part07: new URL('./audio/nordic-07.mp3', import.meta.url).href,
        };
        this.audio = new Audio(this.tracks[this.track]);
        this.audio.preload = 'metadata';
        this.audio.loop = true;
        this.audio.addEventListener('play', () => { this.isPlaying = true; });
        this.audio.addEventListener('pause', () => { this.isPlaying = false; });
    }

    ensureContext() {
        if (this.context) return;
        this.context = new (window.AudioContext || window.webkitAudioContext)();
        this.analyzer = this.context.createAnalyser();
        this.analyzer.fftSize = 256;
        this.dataArray = new Uint8Array(this.analyzer.frequencyBinCount);
        this.master = this.context.createGain();
        this.master.gain.value = 0.16;
        const source = this.context.createMediaElementSource(this.audio);
        source.connect(this.master);
        this.master.connect(this.analyzer);
        this.analyzer.connect(this.context.destination);
    }

    setTrack(track) {
        if (!this.tracks[track]) return;
        const wasPlaying = this.isPlaying;
        this.track = track;
        this.audio.pause();
        this.audio.src = this.tracks[track];
        this.audio.currentTime = 0;
        this.audio.load();
        return wasPlaying;
    }

    async start() {
        this.ensureContext();
        await this.context.resume();
        try {
            await this.audio.play();
            this.isPlaying = true;
            return true;
        } catch (error) {
            this.isPlaying = false;
            return false;
        }
    }

    stop() {
        this.audio.pause();
        this.isPlaying = false;
    }

    update() {
        if (!this.analyzer || !this.dataArray) return 0;
        this.analyzer.getByteFrequencyData(this.dataArray);
        let sum = 0;
        for (let i = 0; i < this.dataArray.length; i += 1) sum += this.dataArray[i];
        this.volume = sum / this.dataArray.length / 255;
        return this.volume;
    }
}

const section = document.querySelector('[data-hero3d]');
const canvas = document.getElementById('hero3d-canvas');

if (section && canvas && window.gsap) {
    const engine = new Engine({ canvas, container: section });
    const player = new AmbientPlayer();
    const launcher = section.querySelector('.hero3d-launch');
    const panel = section.querySelector('.hero3d-audio-panel');
    const micButton = section.querySelector('.hero3d-mic');
    const playButton = section.querySelector('.hero3d-play');
    const state = section.querySelector('[data-audio-state]');
    const tracks = [...section.querySelectorAll('.hero3d-track')];
    let micStarted = false;

    const setState = text => {
        if (state) state.textContent = text;
    };

    const useAnalyzer = analyzer => {
        engine.audio = analyzer;
        setState(analyzer instanceof AmbientPlayer ? 'AMBIENT / LIVE' : 'MIC / LIVE');
    };

    const startAmbient = async () => {
        const started = await player.start();
        if (!started) {
            setState('AUDIO READY');
            return false;
        }
        useAnalyzer(player);
        playButton?.setAttribute('aria-pressed', 'true');
        if (playButton) {
            playButton.textContent = '❚❚';
            playButton.setAttribute('aria-label', 'Pause ambient sound');
        }
        return true;
    };

    const stopAmbient = () => {
        player.stop();
        if (engine.audio === player) engine.audio = null;
        playButton?.setAttribute('aria-pressed', 'false');
        if (playButton) {
            playButton.textContent = '▶';
            playButton.setAttribute('aria-label', 'Play ambient sound');
        }
        setState(micStarted ? 'MIC / LIVE' : 'MIC / AUTO');
    };

    const tryMicrophone = async () => {
        if (micStarted || !navigator.mediaDevices?.getUserMedia) return false;
        try {
            const microphone = new AudioAnalyzer();
            await microphone.init();
            if (player.isPlaying) stopAmbient();
            micStarted = true;
            useAnalyzer(microphone);
            micButton?.setAttribute('aria-pressed', 'true');
            return true;
        } catch (error) {
            setState('AMBIENT READY');
            return false;
        }
    };

    launcher?.addEventListener('click', () => {
        const isOpen = launcher.getAttribute('aria-expanded') === 'true';
        launcher.setAttribute('aria-expanded', String(!isOpen));
        if (panel) panel.hidden = isOpen;
    });
    micButton?.addEventListener('click', async () => {
        const granted = await tryMicrophone();
        if (!granted) setState('MICROPHONE UNAVAILABLE');
    });
    playButton?.addEventListener('click', async () => {
        if (player.isPlaying) stopAmbient();
        else await startAmbient();
    });
    tracks.forEach(button => {
        button.addEventListener('click', async () => {
            tracks.forEach(item => item.classList.toggle('is-active', item === button));
            player.setTrack(button.dataset.track);
            await startAmbient();
        });
    });

    const startPreferredAudio = async () => {
        try {
            const permission = await navigator.permissions?.query({ name: 'microphone' });
            if (permission?.state === 'granted') return tryMicrophone();
        } catch (error) {
            // Some browsers do not expose microphone permission state.
        }
        setState('AUDIO READY');
        return false;
    };

    startPreferredAudio();
    window.addEventListener('pointerdown', () => {
        if (!micStarted) tryMicrophone();
    }, { once: true });
}
