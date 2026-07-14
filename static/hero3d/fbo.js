import * as THREE from './three.module.js';

export class FBO {
    constructor(size, renderer, simulationMaterial, initTexture) {
        this.size = size;
        this.renderer = renderer;
        this.material = simulationMaterial;
        
        this.scene = new THREE.Scene();
        this.camera = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1);
        
        this.geom = new THREE.PlaneGeometry(2, 2);
        this.mesh = new THREE.Mesh(this.geom, this.material);
        this.scene.add(this.mesh);

        this.renderTargetA = this.createTarget();
        this.renderTargetB = this.createTarget();
        
        if (initTexture) {
            const initMaterial = new THREE.ShaderMaterial({
                uniforms: { 
                    u_posTexture: { value: initTexture },
                    u_targetPos: { value: initTexture },
                    u_time: { value: 0 },
                    u_mouse: { value: new THREE.Vector2(0, 0) },
                    u_audio: { value: 0 },
                    u_explosion: { value: 0 }
                },
                vertexShader: `
                    varying vec2 vUv;
                    void main() {
                        vUv = uv;
                        gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
                    }
                `,
                fragmentShader: `
                    uniform sampler2D u_posTexture;
                    uniform float u_time;
                    uniform vec2 u_mouse;
                    uniform float u_audio;
                    uniform float u_explosion;
                    uniform sampler2D u_targetPos;
                    varying vec2 vUv;
                    
                    void main() {
                        gl_FragColor = texture2D(u_posTexture, vUv);
                    }
                `
            });

            const initMesh = new THREE.Mesh(this.geom, initMaterial);
            this.scene.add(initMesh);
            this.mesh.visible = false;

            this.renderer.setRenderTarget(this.renderTargetA);
            this.renderer.render(this.scene, this.camera);
            this.renderer.setRenderTarget(this.renderTargetB);
            this.renderer.render(this.scene, this.camera);
            this.renderer.setRenderTarget(null);

            this.scene.remove(initMesh);
            this.mesh.visible = true;
        }

        this.current = this.renderTargetA;
        this.next = this.renderTargetB;
    }

    createTarget() {
        return new THREE.WebGLRenderTarget(this.size, this.size, {
            minFilter: THREE.NearestFilter,
            magFilter: THREE.NearestFilter,
            format: THREE.RGBAFormat,
            type: THREE.FloatType,
            stencilBuffer: false,
            depthBuffer: false
        });
    }

    update(time) {
        this.material.uniforms.u_posTexture.value = this.current.texture;
        this.material.uniforms.u_time.value = time;

        this.renderer.setRenderTarget(this.next);
        this.renderer.render(this.scene, this.camera);
        this.renderer.setRenderTarget(null);

        let temp = this.current;
        this.current = this.next;
        this.next = temp;
    }

    get texture() {
        return this.current.texture;
    }
}
