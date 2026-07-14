import * as THREE from './three.module.js';
import { simulationVertex, simulationFragment } from './shaders.js';
import { FBO } from './fbo.js';
import { postVertex, postFragment } from './postprocess.js';

export class Engine {
    constructor(options = {}) {
        this.canvas = options.canvas || document.querySelector('#canvas');
        this.container = options.container || this.canvas?.parentElement || document;
        this.scene = new THREE.Scene();
        const bounds = this.getBounds();
        this.camera = new THREE.PerspectiveCamera(75, bounds.width / bounds.height, 0.1, 1000);
        this.renderer = new THREE.WebGLRenderer({
            canvas: this.canvas,
            antialias: false,
            stencil: false,
            depth: true
        });
        
        this.clock = new THREE.Clock();
        this.mouse = new THREE.Vector2();
        this.targetMouse = new THREE.Vector2();
        this.currentScene = 0;
        this.isTransitioning = false;
        this.audio = null;
        this.animationFrame = null;
        this.init();
    }

    getBounds() {
        const rect = this.container.getBoundingClientRect ? this.container.getBoundingClientRect() : null;
        return {
            width: Math.max(1, rect?.width || window.innerWidth),
            height: Math.max(1, rect?.height || window.innerHeight)
        };
    }

    init() {
        const bounds = this.getBounds();
        this.renderer.setSize(bounds.width, bounds.height);
        this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
        this.camera.position.z = 2;

        this.mainTarget = new THREE.WebGLRenderTarget(bounds.width, bounds.height, {
            format: THREE.RGBAFormat,
            type: THREE.HalfFloatType
        });

        this.backTarget = this.mainTarget.clone();

        this.simMaterial = new THREE.ShaderMaterial({
            uniforms: {
                u_posTexture: { value: null },
                u_targetPos: { value: null },
                u_time: { value: 0 },
                u_mouse: { value: this.mouse },
                u_audio: { value: 0 },
                u_explosion: { value: 0 }
            },
            vertexShader: simulationVertex,
            fragmentShader: simulationFragment
        });

        this.postMaterial = new THREE.ShaderMaterial({
            uniforms: {
                tDiffuse: { value: null },
                tPrev: { value: null },
                uTime: { value: 0 }
            },
            vertexShader: postVertex,
            fragmentShader: postFragment
        });

        this.postScene = new THREE.Scene();
        this.postCamera = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1);
        this.postQuad = new THREE.Mesh(new THREE.PlaneGeometry(2, 2), this.postMaterial);
        this.postScene.add(this.postQuad);

        const size = 128;
        const data1 = new Float32Array(size * size * 4);
        const data2 = new Float32Array(size * size * 4);

        for (let i = 0; i < size * size; i++) {
            const phi = Math.acos(-1 + (2 * i) / (size * size));
            const theta = Math.sqrt(size * size * Math.PI) * phi;
            data1[i * 4] = Math.cos(theta) * Math.sin(phi);
            data1[i * 4 + 1] = Math.sin(theta) * Math.sin(phi);
            data1[i * 4 + 2] = Math.cos(phi);
            data1[i * 4 + 3] = 1.0;

            data2[i * 4] = (Math.random() - 0.5) * 2.0;
            data2[i * 4 + 1] = (Math.random() - 0.5) * 2.0;
            data2[i * 4 + 2] = (Math.random() - 0.5) * 2.0;
            data2[i * 4 + 3] = 1.0;
        }

        const texture1 = new THREE.DataTexture(data1, size, size, THREE.RGBAFormat, THREE.FloatType);
        const texture2 = new THREE.DataTexture(data2, size, size, THREE.RGBAFormat, THREE.FloatType);
        texture1.needsUpdate = true;
        texture2.needsUpdate = true;

        this.simMaterial.uniforms.u_targetPos = { value: texture2 };

        this.createParticles(size, texture1);
        this.animate();

        window.addEventListener('resize', () => this.resize());

        window.addEventListener('mousemove', (e) => {
            const rect = this.container.getBoundingClientRect();
            this.targetMouse.x = ((e.clientX - rect.left) / Math.max(1, rect.width)) * 2 - 1;
            this.targetMouse.y = -(((e.clientY - rect.top) / Math.max(1, rect.height)) * 2 - 1);
            
            const cursor = this.container.querySelector('[data-hero3d-cursor]');
            if(cursor) {
                cursor.style.left = (e.clientX - rect.left) + 'px';
                cursor.style.top = (e.clientY - rect.top) + 'px';
            }
        });
    }

    resize() {
        const bounds = this.getBounds();
        this.camera.aspect = bounds.width / bounds.height;
        this.camera.updateProjectionMatrix();
        this.renderer.setSize(bounds.width, bounds.height);
        this.mainTarget.setSize(bounds.width, bounds.height);
        this.backTarget.setSize(bounds.width, bounds.height);
    }

    nextScene() {
        if (this.isTransitioning) return;
        this.isTransitioning = true;

        gsap.to(this.camera.position, {
            z: 1.5,
            duration: 1.0,
            yoyo: true,
            repeat: 1,
            ease: "power2.inOut"
        });

        gsap.to(this.simMaterial.uniforms.u_explosion, {
            value: 1.0,
            duration: 1.2,
            ease: "power2.in",
            onComplete: () => {
                this.currentScene = (this.currentScene + 1) % 2;
                
                gsap.to(this.simMaterial.uniforms.u_explosion, {
                    value: 0.05,
                    duration: 1.5,
                    ease: "elastic.out(1, 0.3)",
                    onComplete: () => {
                        this.isTransitioning = false;
                    }
                });
            }
        });
    }

    createParticles(size, initTexture) {
        this.fbo = new FBO(size, this.renderer, this.simMaterial, initTexture);
        
        const geometry = new THREE.BufferGeometry();
        const positions = new Float32Array(size * size * 3);
        const uvs = new Float32Array(size * size * 2);

        for(let i=0; i < size * size; i++) {
            uvs[i*2] = (i % size) / size;
            uvs[i*2+1] = Math.floor(i / size) / size;
        }

        geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
        geometry.setAttribute('uv', new THREE.BufferAttribute(uvs, 2));

        this.renderMaterial = new THREE.ShaderMaterial({
            uniforms: {
                u_posTexture: { value: null },
                u_time: { value: 0 },
                u_audio: { value: 0 },
                u_color1: { value: new THREE.Color("#00ffff") },
                u_color2: { value: new THREE.Color("#ff00ff") }
            },
            vertexShader: `
                uniform sampler2D u_posTexture;
                uniform float u_time;
                uniform float u_audio;
                varying float vVelocity;
                varying vec2 vUv;

                void main() {
                    vUv = uv;
                    vec4 pos = texture2D(u_posTexture, uv);
                    
                    vVelocity = length(pos.xyz) * 0.5;

                    vec4 mvPosition = modelViewMatrix * vec4(pos.xyz, 1.0);
                    
                    gl_PointSize = (2.0 / -mvPosition.z) * (1.0 + vVelocity) + u_audio * 10.0;
                    gl_Position = projectionMatrix * mvPosition;
                }
            `,
            fragmentShader: `
                uniform vec3 u_color1;
                uniform vec3 u_color2;
                uniform float u_audio;
                varying float vVelocity;

                void main() {
                    float dist = length(gl_PointCoord - vec2(0.5));
                    if (dist > 0.5) discard;

                    vec3 finalColor = mix(u_color1, u_color2, clamp(vVelocity, 0.0, 1.0));
                    
                    float alpha = smoothstep(0.5, 0.1, dist) * (0.5 + u_audio * 1.5);
                    
                    gl_FragColor = vec4(finalColor, alpha);
                }
            `,
            transparent: true,
            blending: THREE.AdditiveBlending,
            depthTest: false
        });

        this.points = new THREE.Points(geometry, this.renderMaterial);
        this.scene.add(this.points);
    }

    animate() {
        this.animationFrame = requestAnimationFrame(() => this.animate());
        const delta = this.clock.getElapsedTime();
        
        this.mouse.x += (this.targetMouse.x - this.mouse.x) * 0.05;
        this.mouse.y += (this.targetMouse.y - this.mouse.y) * 0.05;
        
        this.camera.position.x += (this.mouse.x * 0.5 - this.camera.position.x) * 0.05;
        this.camera.position.y += (-this.mouse.y * 0.5 - this.camera.position.y) * 0.05;
        this.camera.lookAt(0, 0, 0);
        
        const title = this.container.querySelector('[data-hero3d-title]');
        if(title) {
            title.style.transform = `translate(${this.mouse.x * 50}px, ${-this.mouse.y * 50}px)`;
        }
        
        let volume = 0;
        if(this.audio) {
            volume = this.audio.update();
            this.simMaterial.uniforms.u_audio.value = volume;
            this.renderMaterial.uniforms.u_audio.value = volume;
        }
        
        this.renderMaterial.uniforms.u_time.value = delta;
        this.fbo.update(delta);
        this.renderMaterial.uniforms.u_posTexture.value = this.fbo.texture;

        this.renderer.setRenderTarget(this.mainTarget);
        this.renderer.render(this.scene, this.camera);

        this.postMaterial.uniforms.tDiffuse.value = this.mainTarget.texture;
        this.postMaterial.uniforms.tPrev.value = this.backTarget.texture;
        this.postMaterial.uniforms.uTime.value = delta;

        this.renderer.setRenderTarget(null);
        this.renderer.render(this.postScene, this.postCamera);

        let temp = this.mainTarget;
        this.mainTarget = this.backTarget;
        this.backTarget = temp;
    }
}
