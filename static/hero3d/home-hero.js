import { Engine } from './gl.js';
import { AudioAnalyzer } from './audio.js';

class AmbientPlayer {
    constructor() {
        this.context = null;
        this.analyzer = null;
        this.master = null;
        this.dataArray = null;
        this.volume = 0;
        this.pendingVolume = 0.16;
        this.track = 'part01';
        this.isPlaying = false;
        this.tracks = Object.fromEntries(
            Array.from({ length: 7 }, (_, index) => {
                const number = String(index + 1).padStart(2, '0');
                return [`part${number}`, new URL(`./audio/nordic-${number}.mp3`, import.meta.url).href];
            }),
        );
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
        this.master.gain.value = this.pendingVolume;
        const source = this.context.createMediaElementSource(this.audio);
        source.connect(this.master);
        this.master.connect(this.analyzer);
        this.analyzer.connect(this.context.destination);
    }

    setTrack(track) {
        if (!this.tracks[track]) return false;
        this.track = track;
        this.audio.pause();
        this.audio.src = this.tracks[track];
        this.audio.currentTime = 0;
        this.audio.load();
        return true;
    }

    setVolume(value) {
        const normalised = Math.max(0, Math.min(1, Number(value) / 100));
        this.pendingVolume = normalised;
        if (this.master) this.master.gain.value = normalised;
    }

    async start() {
        this.ensureContext();
        await this.context.resume();
        try {
            await this.audio.play();
            this.isPlaying = true;
            return true;
        } catch {
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
    const micNote = section.querySelector('[data-mic-note]');
    const micEnable = section.querySelector('[data-mic-enable]');
    const micDismiss = section.querySelector('[data-mic-dismiss]');
    const playButton = section.querySelector('.hero3d-play');
    const state = section.querySelector('[data-audio-state]');
    const trackName = section.querySelector('[data-track-name]');
    const volumeControl = section.querySelector('.hero3d-volume');
    const tracks = [...section.querySelectorAll('.hero3d-track')];
    const localized = document.getElementById('premium-audio-copy')?.dataset || {};
    const ui = {
        play: localized.play || 'Play ambient sound',
        pause: localized.pause || 'Pause ambient sound',
        ambientLive: localized.ambientLive || 'AMBIENT / LIVE',
        micLive: localized.micLive || 'MIC / LIVE',
        micOff: localized.micOff || 'MIC / OFF',
        micStop: localized.micStop || 'Stop microphone reaction',
        micUnavailable: localized.micUnavailable || 'MICROPHONE UNAVAILABLE',
        motionReduced: localized.motionReduced || 'MOTION REDUCED',
        ready: localized.ready || 'AUDIO READY',
        signal: localized.signal || 'Ambient signal',
        track: localized.track || 'Nordic music part',
    };
    const reducedMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)');
    let microphone = null;
    let micPromptSeen = false;
    const trackNames = {
        part01: 'Nordic Ritual I', part02: 'Nordic Ritual II', part03: 'Nordic Ritual III',
        part04: 'Nordic Ritual IV', part05: 'Nordic Ritual V', part06: 'Nordic Ritual VI', part07: 'Nordic Ritual VII',
    };

    const setState = text => { if (state) state.textContent = text; };
    const emitMicEvent = (event, detail = {}) => {
        try {
            const payload = { surface: 'home', ...detail };
            const customEvent = new CustomEvent(`nexora:mic-${event}`, { detail: payload });
            section.dispatchEvent(customEvent);
            window.dispatchEvent(new CustomEvent(`nexora:mic-${event}`, { detail: payload }));
        } catch {
            // Optional integration hooks must never break the hero experience.
        }
    };
    const closeMicNote = () => {
        if (micNote) micNote.hidden = true;
    };
    const openMicNote = () => {
        if (!micNote) return;
        micPromptSeen = true;
        micNote.hidden = false;
        micEnable?.focus();
        emitMicEvent('prompt-shown');
    };
    const setPlayButton = playing => {
        playButton?.setAttribute('aria-pressed', String(playing));
        if (!playButton) return;
        playButton.textContent = playing ? '❚❚' : '▶';
        playButton.setAttribute('aria-label', playing ? ui.pause : ui.play);
    };
    const useAnalyzer = analyzer => {
        engine.audio = analyzer;
        setState(analyzer instanceof AmbientPlayer ? ui.ambientLive : ui.micLive);
    };
    const stopMicrophone = () => {
        microphone?.stop?.();
        microphone = null;
        closeMicNote();
        if (!(engine.audio instanceof AmbientPlayer)) engine.audio = null;
        micButton?.setAttribute('aria-pressed', 'false');
        micButton?.setAttribute('aria-label', localized.microphoneReaction || ui.micOff);
        setState(player.isPlaying ? ui.ambientLive : ui.micOff);
        emitMicEvent('stopped');
    };
    const stopAmbient = () => {
        player.stop();
        if (engine.audio === player) engine.audio = null;
        setPlayButton(false);
        setState(microphone ? ui.micLive : ui.ready);
    };
    const startAmbient = async () => {
        if (microphone) stopMicrophone();
        const started = await player.start();
        if (!started) {
            setState(ui.ready);
            return false;
        }
        useAnalyzer(player);
        setPlayButton(true);
        return true;
    };
    const startMicrophone = async () => {
        if (microphone) return false;
        if (!navigator.mediaDevices?.getUserMedia) {
            setState(ui.micUnavailable);
            emitMicEvent('fallback', { reason: 'unsupported' });
            return false;
        }
        try {
            emitMicEvent('permission-requested');
            microphone = new AudioAnalyzer();
            await microphone.init();
            if (player.isPlaying) stopAmbient();
            useAnalyzer(microphone);
            micButton?.setAttribute('aria-pressed', 'true');
            micButton?.setAttribute('aria-label', ui.micStop);
            closeMicNote();
            emitMicEvent('permission-granted');
            emitMicEvent('started');
            return true;
        } catch (error) {
            microphone = null;
            setState(ui.micUnavailable);
            if (error?.name === 'NotAllowedError' || error?.name === 'SecurityError') {
                emitMicEvent('permission-denied');
            }
            emitMicEvent('fallback', { reason: 'unavailable' });
            return false;
        }
    };

    launcher?.addEventListener('click', () => {
        const isOpen = launcher.getAttribute('aria-expanded') === 'true';
        launcher.setAttribute('aria-expanded', String(!isOpen));
        if (panel) panel.hidden = isOpen;
    });
    micButton?.addEventListener('click', async () => {
        if (microphone) {
            stopMicrophone();
            return;
        }
        if (!micPromptSeen && micNote) {
            openMicNote();
            return;
        }
        await startMicrophone();
    });
    micEnable?.addEventListener('click', async () => {
        await startMicrophone();
    });
    micDismiss?.addEventListener('click', () => {
        closeMicNote();
        micButton?.focus();
    });
    playButton?.addEventListener('click', () => {
        if (player.isPlaying) stopAmbient();
        else startAmbient();
    });
    tracks.forEach(button => {
        button.addEventListener('click', () => {
            const selectedTrack = button.dataset.track;
            if (!player.setTrack(selectedTrack)) return;
            tracks.forEach(item => item.classList.toggle('is-active', item === button));
            if (trackName) trackName.textContent = `${ui.track} ${Number(selectedTrack.slice(-2))}`;
            startAmbient();
        });
    });
    volumeControl?.addEventListener('input', event => player.setVolume(event.currentTarget.value));

    const syncReducedMotion = () => {
        if (reducedMotion?.matches) {
            engine.isVisible = false;
            engine.syncAnimationState();
            section.querySelector('video')?.pause();
            setState(ui.motionReduced);
        } else {
            engine.isVisible = true;
            engine.syncAnimationState();
            setState(player.isPlaying ? ui.ambientLive : ui.ready);
        }
    };
    reducedMotion?.addEventListener?.('change', syncReducedMotion);
    syncReducedMotion();
    document.addEventListener('keydown', event => {
        if (event.key === 'Escape') closeMicNote();
    });
    window.addEventListener('pagehide', () => {
        player.stop();
        stopMicrophone();
        engine.dispose();
    }, { once: true });
}
