import * as THREE from './three.module.js';

export const postVertex = `
    varying vec2 vUv;
    void main() {
        vUv = uv;
        gl_Position = vec4(position, 1.0);
    }
`;

export const postFragment = `
    precision highp float;
    uniform sampler2D tDiffuse;
    uniform sampler2D tPrev;
    uniform float uTime;
    varying vec2 vUv;

    void main() {
        vec4 scene = texture2D(tDiffuse, vUv);
        vec4 prev = texture2D(tPrev, vUv);

        vec4 trail = prev * 0.93;

        vec4 finalColor = max(scene, trail);

        gl_FragColor = finalColor;
    }
`;
