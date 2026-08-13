import { browserExperiencePolicy } from './performance-policy.mjs';

const experience = browserExperiencePolicy();
const THREE = experience.webgl ? await import('./hero3d/three.module.js') : null;

/*
 * The catalogue is a small 3D media constellation, not a conventional slider.
 * It only uses product images already rendered by Django, keeps the DOM collage
 * as a no-WebGL fallback and pauses when off screen or in a hidden tab.
 */
const stage = document.querySelector('[data-catalog-webgl]');
const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');

if (stage && THREE && !reducedMotion.matches && window.innerWidth > 1040) {
    const canvas = stage.querySelector('.catalog-webgl-canvas');
    const sources = [...stage.querySelectorAll('.catalog-motion-card img')]
        .map(image => image.currentSrc || image.src)
        .filter(Boolean);

    try {
        const renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: true, powerPreference: 'high-performance' });
        renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.35));
        renderer.outputColorSpace = THREE.SRGBColorSpace;

        const scene = new THREE.Scene();
        const camera = new THREE.PerspectiveCamera(37, 1, .1, 100);
        camera.position.set(0, .08, 7.2);
        const world = new THREE.Group();
        scene.add(world);
        const clock = new THREE.Clock();
        const pointer = new THREE.Vector2();
        const targetPointer = new THREE.Vector2();
        const cards = [];
        let visible = true;
        let pageVisible = !document.hidden;
        let frame = 0;

        // Deliberately irregular positions create a curated constellation rather
        // than a visual grid. The final value is depth, which drives parallax.
        const layout = [
            [-2.62,  .56, -1.35, .78, -.18], [-1.55, 1.44,  .40, .52,  .15],
            [-.42,  .76,  1.18, .96, -.10], [ .82, 1.50, -.22, .48,  .16],
            [ 2.08, .71,  .86, .67, -.13], [-2.13,-.84,  .36, .50,  .10],
            [-.92,-.53, -1.08, .86, -.17], [ .29,-1.33,  .63, .54,  .08],
            [ 1.55,-.55,  1.28, .68, -.07], [ 2.64,-1.16, -.12, .44, .13],
            [-2.93, 1.50, .88, .38, -.08], [ .10, 2.06,-.54, .58, .08],
            [ 2.48, 1.73, 1.08, .43, -.11], [ 3.00, .04,-.58, .34, .10],
        ];

        const resize = () => {
            const { width, height } = stage.getBoundingClientRect();
            renderer.setSize(width, height, false);
            camera.aspect = width / Math.max(height, 1);
            camera.updateProjectionMatrix();
        };

        const textureLoader = new THREE.TextureLoader();
        sources.forEach((source, index) => {
            const [x, y, z, scale, tilt] = layout[index % layout.length];
            textureLoader.load(source, texture => {
                texture.colorSpace = THREE.SRGBColorSpace;
                const aspect = Math.max(.66, Math.min(1.6, texture.image.width / texture.image.height));
                const material = new THREE.MeshBasicMaterial({
                    map: texture,
                    transparent: true,
                    opacity: index % 5 === 2 ? .96 : .76,
                    depthWrite: false,
                });
                const mesh = new THREE.Mesh(new THREE.PlaneGeometry(aspect, 1), material);
                mesh.position.set(x, y, z);
                mesh.rotation.z = tilt;
                mesh.scale.setScalar(scale);
                world.add(mesh);
                cards.push({ mesh, x, y, z, scale, tilt, phase: index * .77, drift: .13 + (index % 4) * .035 });
            });
        });

        // Warm titanium particles give the scene depth and gentle life. A tiny
        // shader makes every point breathe at a different intensity.
        const points = 96;
        const positions = new Float32Array(points * 3);
        const phases = new Float32Array(points);
        for (let index = 0; index < points; index += 1) {
            positions[index * 3] = (Math.random() - .5) * 7.4;
            positions[index * 3 + 1] = (Math.random() - .5) * 4.8;
            positions[index * 3 + 2] = -1.5 + Math.random() * 3.8;
            phases[index] = Math.random() * Math.PI * 2;
        }
        const dustGeometry = new THREE.BufferGeometry();
        dustGeometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
        dustGeometry.setAttribute('aPhase', new THREE.BufferAttribute(phases, 1));
        const dustMaterial = new THREE.ShaderMaterial({
            transparent: true,
            depthWrite: false,
            uniforms: { uTime: { value: 0 } },
            vertexShader: `attribute float aPhase; uniform float uTime; varying float vGlow; void main(){ vGlow=.38+.62*(.5+.5*sin(uTime*.72+aPhase)); vec4 p=modelViewMatrix*vec4(position,1.); gl_PointSize=(1.7+vGlow*2.1)*(7./-p.z); gl_Position=projectionMatrix*p; }`,
            fragmentShader: `varying float vGlow; void main(){ float d=length(gl_PointCoord-vec2(.5)); float a=smoothstep(.5,.04,d)*vGlow*.58; gl_FragColor=vec4(vec3(.96,.72,.46),a); }`,
        });
        world.add(new THREE.Points(dustGeometry, dustMaterial));

        const onPointerMove = event => {
            const rect = stage.getBoundingClientRect();
            targetPointer.set(
                ((event.clientX - rect.left) / Math.max(rect.width, 1) - .5) * 2,
                ((event.clientY - rect.top) / Math.max(rect.height, 1) - .5) * 2,
            );
        };
        stage.addEventListener('pointermove', onPointerMove, { passive: true });
        stage.addEventListener('pointerleave', () => targetPointer.set(0, 0), { passive: true });
        const resizeObserver = new ResizeObserver(resize);
        resizeObserver.observe(stage);
        const visibilityObserver = new IntersectionObserver(([entry]) => {
            visible = entry.isIntersecting;
            if (visible && pageVisible) render();
        }, { threshold: .04 });
        visibilityObserver.observe(stage);
        document.addEventListener('visibilitychange', () => {
            pageVisible = !document.hidden;
            if (pageVisible && visible) render();
        });
        resize();
        stage.classList.add('is-webgl-ready');

        const render = () => {
            if (frame || !visible || !pageVisible) return;
            frame = requestAnimationFrame(() => {
                frame = 0;
                if (!visible || !pageVisible) return;
                const time = clock.getElapsedTime();
                pointer.lerp(targetPointer, .055);
                // This is a camera-like 360° orbit, intentionally restrained so
                // the product images remain legible and clickable nearby.
                world.rotation.y += (pointer.x * .34 - world.rotation.y) * .045;
                world.rotation.x += (-pointer.y * .18 - world.rotation.x) * .045;
                world.rotation.z = Math.sin(time * .14) * .018;
                cards.forEach(card => {
                    const wave = Math.sin(time * card.drift + card.phase);
                    const sway = Math.cos(time * card.drift * .78 + card.phase);
                    card.mesh.position.x = card.x + sway * .075;
                    card.mesh.position.y = card.y + wave * .11;
                    card.mesh.rotation.z = card.tilt + wave * .028;
                    const breathe = 1 + wave * .026;
                    card.mesh.scale.setScalar(card.scale * breathe);
                });
                dustMaterial.uniforms.uTime.value = time;
                renderer.render(scene, camera);
                render();
            });
        };
        render();
    } catch (error) {
        // The accessible DOM collage stays available if WebGL is unsupported.
        console.warn('Catalog WebGL is unavailable; using the media fallback.', error);
    }
}
