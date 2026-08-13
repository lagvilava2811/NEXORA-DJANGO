import { AudioAnalyzer } from './audio.js';
import { browserExperiencePolicy } from '../performance-policy.mjs';

const experience = browserExperiencePolicy();
const { Engine } = experience.webgl ? await import('./gl.js') : { Engine: null };

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
    section.dataset.experienceTier = experience.tier;
    const engine = Engine ? new Engine({ canvas, container: section }) : null;
    const player = new AmbientPlayer();
    const launcher = section.querySelector('.hero3d-launch');
    const panel = section.querySelector('.hero3d-audio-panel');
    const micButton = section.querySelector('.hero3d-mic');
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
    const trackNames = {
        part01: 'Nordic Ritual I', part02: 'Nordic Ritual II', part03: 'Nordic Ritual III',
        part04: 'Nordic Ritual IV', part05: 'Nordic Ritual V', part06: 'Nordic Ritual VI', part07: 'Nordic Ritual VII',
    };

    const setState = text => { if (state) state.textContent = text; };
    const setPlayButton = playing => {
        playButton?.setAttribute('aria-pressed', String(playing));
        if (!playButton) return;
        playButton.textContent = playing ? '❚❚' : '▶';
        playButton.setAttribute('aria-label', playing ? ui.pause : ui.play);
    };
    const useAnalyzer = analyzer => {
        if (engine) engine.audio = analyzer;
        setState(analyzer instanceof AmbientPlayer ? ui.ambientLive : ui.micLive);
    };
    const stopMicrophone = () => {
        microphone?.stop?.();
        microphone = null;
        if (engine && !(engine.audio instanceof AmbientPlayer)) engine.audio = null;
        micButton?.setAttribute('aria-pressed', 'false');
        micButton?.setAttribute('aria-label', localized.microphoneReaction || ui.micOff);
        setState(player.isPlaying ? ui.ambientLive : ui.micOff);
    };
    const stopAmbient = () => {
        player.stop();
        if (engine?.audio === player) engine.audio = null;
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
        if (microphone || !navigator.mediaDevices?.getUserMedia) return false;
        try {
            microphone = new AudioAnalyzer();
            await microphone.init();
            if (player.isPlaying) stopAmbient();
            useAnalyzer(microphone);
            micButton?.setAttribute('aria-pressed', 'true');
            micButton?.setAttribute('aria-label', ui.micStop);
            return true;
        } catch {
            microphone = null;
            setState(ui.micUnavailable);
            return false;
        }
    };

    launcher?.addEventListener('click', () => {
        const isOpen = launcher.getAttribute('aria-expanded') === 'true';
        launcher.setAttribute('aria-expanded', String(!isOpen));
        if (panel) panel.hidden = isOpen;
    });
    micButton?.addEventListener('click', async () => {
        if (microphone) stopMicrophone();
        else await startMicrophone();
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
            if (engine) {
                engine.isVisible = false;
                engine.syncAnimationState();
            }
            section.querySelector('video')?.pause();
            setState(ui.motionReduced);
        } else {
            if (engine) {
                engine.isVisible = true;
                engine.syncAnimationState();
            }
            setState(player.isPlaying ? ui.ambientLive : ui.ready);
        }
    };
    reducedMotion?.addEventListener?.('change', syncReducedMotion);
    syncReducedMotion();
    window.addEventListener('pagehide', () => {
        player.stop();
        stopMicrophone();
        engine?.dispose();
    }, { once: true });

    const ambientVideo = document.querySelector('[data-adaptive-video]');
    if (ambientVideo && experience.ambientVideo) {
        const videoObserver = new IntersectionObserver(([entry]) => {
            if (entry.isIntersecting) ambientVideo.play().catch(() => {});
            else ambientVideo.pause();
        }, { rootMargin: '160px 0px', threshold: 0.05 });
        videoObserver.observe(ambientVideo);
        window.addEventListener('pagehide', () => videoObserver.disconnect(), { once: true });
    }
}
