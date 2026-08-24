import * as THREE from './hero3d/three.module.js';
import { GLTFLoader } from './nexora-morph/vendor/GLTFLoader.js';

const root = document.querySelector('[data-nexora-morph]');

if (root) {
  const canvas = root.querySelector('[data-morph-canvas]');
  const stage = root.querySelector('[data-morph-stage]');
  const controls = [...root.querySelectorAll('[data-morph-select]')];
  const name = root.querySelector('[data-morph-name]');
  const position = root.querySelector('[data-morph-position]');
  const status = root.querySelector('[data-morph-status]');
  const loading = root.querySelector('[data-morph-loading]');
  const reduceMotion = matchMedia('(prefers-reduced-motion: reduce)');
  const modelBase = root.dataset.modelBase || '/static/nexora-morph/models/';
  const models = controls.map((control) => ({
    label: control.dataset.label || control.textContent.trim(),
    file: control.dataset.model,
    url: control.dataset.modelUrl || `${modelBase}${control.dataset.model}`,
  }));

  if (canvas && stage && models.length) {
    const renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: true, powerPreference: 'high-performance' });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.12;
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    renderer.setClearColor(0x000000, 0);

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(31, 1, 0.1, 50);
    camera.position.set(0, 0.08, 7.2);
    camera.lookAt(0, 0, 0);

    const rig = new THREE.Group();
    scene.add(rig);

    scene.add(new THREE.HemisphereLight(0xf6f1e7, 0x12151d, 2.2));
    const key = new THREE.DirectionalLight(0xfff4e8, 5.2);
    key.position.set(3.6, 4.8, 5.4);
    key.castShadow = true;
    key.shadow.mapSize.set(1024, 1024);
    key.shadow.camera.near = 0.1;
    key.shadow.camera.far = 18;
    scene.add(key);
    const rim = new THREE.DirectionalLight(0xff5a3d, 4.1);
    rim.position.set(-5.5, 1.8, -3.2);
    scene.add(rim);
    const soft = new THREE.PointLight(0xaec4ff, 22, 16, 2);
    soft.position.set(-3.4, -0.9, 4.2);
    scene.add(soft);

    const floor = new THREE.Mesh(
      new THREE.CircleGeometry(2.35, 96),
      new THREE.ShadowMaterial({ color: 0x000000, opacity: 0.28 }),
    );
    floor.rotation.x = -Math.PI / 2;
    floor.position.y = -1.72;
    floor.receiveShadow = true;
    scene.add(floor);

    const loader = new GLTFLoader();
    const cache = new Map();
    const modelProfiles = {
      'laptop.glb': { size: 4.4, yaw: -0.52, pitch: -0.06, y: -0.05 },
      'headphones.glb': { size: 3.8, yaw: -0.34, pitch: 0.02, y: -0.02 },
      'camera.glb': { size: 3.85, yaw: -0.5, pitch: -0.04, y: -0.03 },
    };

    let active = 0;
    let requested = 0;
    let currentModel = null;
    let transition = null;
    let dragging = false;
    let pointerX = 0;
    let pointerY = 0;
    let yaw = modelProfiles[models[0].file]?.yaw || 0;
    let pitch = modelProfiles[models[0].file]?.pitch || 0;
    let targetYaw = yaw;
    let targetPitch = pitch;
    let idleSince = performance.now();
    let animationFrame = null;
    let stageVisible = true;

    const setMaterialOpacity = (object, opacity) => {
      object.traverse((child) => {
        if (!child.isMesh) return;
        child.castShadow = true;
        child.receiveShadow = true;
        const materials = Array.isArray(child.material) ? child.material : [child.material];
        materials.forEach((material) => {
          if (!material) return;
          material.transparent = opacity < 0.999;
          material.opacity = opacity;
          material.depthWrite = opacity > 0.55;
          material.needsUpdate = true;
          if ('envMapIntensity' in material) material.envMapIntensity = 1.25;
          if ('roughness' in material) material.roughness = Math.max(0.22, material.roughness ?? 0.5);
        });
      });
    };

    const prepareModel = (gltf, file) => {
      const profile = modelProfiles[file] || { size: 3.9, yaw: 0, pitch: 0, y: 0 };
      const content = gltf.scene;
      content.traverse((child) => {
        if (!child.isMesh) return;
        child.material = Array.isArray(child.material)
          ? child.material.map((material) => material.clone())
          : child.material?.clone();
      });
      content.updateMatrixWorld(true);
      const bounds = new THREE.Box3().setFromObject(content);
      const center = bounds.getCenter(new THREE.Vector3());
      const dimensions = bounds.getSize(new THREE.Vector3());
      const longestSide = Math.max(dimensions.x, dimensions.y, dimensions.z, 0.001);
      content.position.copy(center).multiplyScalar(-1);

      const wrapper = new THREE.Group();
      wrapper.add(content);
      wrapper.scale.setScalar(profile.size / longestSide);
      wrapper.position.y = profile.y;
      wrapper.rotation.set(profile.pitch, profile.yaw, 0);
      wrapper.userData.profile = profile;
      wrapper.userData.baseScale = wrapper.scale.x;
      setMaterialOpacity(wrapper, 0);
      return wrapper;
    };

    const loadModel = (index) => {
      if (cache.has(index)) return cache.get(index);
      const promise = new Promise((resolve, reject) => {
        loader.load(models[index].url, (gltf) => resolve(prepareModel(gltf, models[index].file)), undefined, reject);
      });
      cache.set(index, promise);
      return promise;
    };

    const setState = (index, busy = false) => {
      controls.forEach((control, controlIndex) => {
        const selected = controlIndex === index;
        control.classList.toggle('is-active', selected);
        control.setAttribute('aria-pressed', String(selected));
      });
      name.textContent = models[index].label;
      position.textContent = `${String(index + 1).padStart(2, '0')} / ${String(models.length).padStart(2, '0')}`;
      loading.hidden = !busy;
      root.classList.toggle('is-loading', busy);
      root.setAttribute('aria-busy', String(busy));
    };

    const showModel = async (next, { announce = true } = {}) => {
      requested = (next + models.length) % models.length;
      const targetIndex = requested;
      setState(targetIndex, true);
      try {
        const incoming = await loadModel(targetIndex);
        if (requested !== targetIndex) return;
        if (incoming.parent) incoming.parent.remove(incoming);
        rig.add(incoming);
        const profile = incoming.userData.profile;
        targetYaw = profile.yaw;
        targetPitch = profile.pitch;
        yaw = targetYaw;
        pitch = targetPitch;
        incoming.rotation.set(pitch, yaw, 0);
        incoming.position.y = profile.y - 0.12;
        incoming.scale.setScalar(incoming.userData.baseScale * 0.88);
        setMaterialOpacity(incoming, reduceMotion.matches ? 1 : 0);

        const outgoing = currentModel;
        currentModel = incoming;
        active = targetIndex;
        transition = reduceMotion.matches ? null : { incoming, outgoing, started: performance.now(), duration: 680 };
        if (reduceMotion.matches) {
          if (outgoing && outgoing !== incoming) rig.remove(outgoing);
          incoming.position.y = profile.y;
          incoming.scale.setScalar(incoming.userData.baseScale);
        }
        setState(active, false);
        root.classList.add('is-ready');
        root.classList.remove('has-error');
        idleSince = performance.now();
        if (announce) status.textContent = models[active].label;
        const preloadIndex = (active + 1) % models.length;
        window.requestIdleCallback?.(() => loadModel(preloadIndex).catch(() => {}), { timeout: 3000 });
      } catch (error) {
        console.error('NEXORA solid model failed to load', error);
        root.classList.add('has-error');
        setState(active, false);
        loading.hidden = false;
        loading.textContent = root.dataset.errorLabel || '3D model unavailable';
      }
    };

    const resize = () => {
      const width = Math.max(1, stage.clientWidth);
      const height = Math.max(1, stage.clientHeight);
      renderer.setSize(width, height, false);
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
    };

    controls.forEach((control, index) => control.addEventListener('click', () => showModel(index)));
    root.addEventListener('keydown', (event) => {
      if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
      event.preventDefault();
      if (event.key === 'Home') showModel(0);
      else if (event.key === 'End') showModel(models.length - 1);
      else showModel(active + (event.key === 'ArrowRight' ? 1 : -1));
    });

    canvas.addEventListener('pointerdown', (event) => {
      dragging = true;
      pointerX = event.clientX;
      pointerY = event.clientY;
      canvas.setPointerCapture(event.pointerId);
      root.classList.add('is-dragging');
    });
    canvas.addEventListener('pointermove', (event) => {
      if (!dragging) return;
      targetYaw += (event.clientX - pointerX) * 0.012;
      targetPitch = THREE.MathUtils.clamp(targetPitch + (event.clientY - pointerY) * 0.004, -0.34, 0.3);
      pointerX = event.clientX;
      pointerY = event.clientY;
      idleSince = performance.now();
    });
    const finishDrag = (event) => {
      dragging = false;
      root.classList.remove('is-dragging');
      if (event?.pointerId !== undefined && canvas.hasPointerCapture(event.pointerId)) canvas.releasePointerCapture(event.pointerId);
      idleSince = performance.now();
    };
    canvas.addEventListener('pointerup', finishDrag);
    canvas.addEventListener('pointercancel', finishDrag);
    window.addEventListener('resize', resize, { passive: true });
    new ResizeObserver(resize).observe(stage);

    const easeOut = (value) => 1 - Math.pow(1 - value, 4);
    const requestNextFrame = () => {
      if (!animationFrame && stageVisible && !document.hidden) {
        animationFrame = requestAnimationFrame(frame);
      }
    };
    const frame = (now) => {
      animationFrame = null;
      if (transition) {
        const progress = Math.min(1, (now - transition.started) / transition.duration);
        const eased = easeOut(progress);
        const { incoming, outgoing } = transition;
        const profile = incoming.userData.profile;
        incoming.position.y = THREE.MathUtils.lerp(profile.y - 0.12, profile.y, eased);
        incoming.scale.setScalar(incoming.userData.baseScale * THREE.MathUtils.lerp(0.88, 1, eased));
        setMaterialOpacity(incoming, eased);
        if (outgoing && outgoing !== incoming) {
          setMaterialOpacity(outgoing, 1 - eased);
          outgoing.scale.multiplyScalar(1.0015);
        }
        if (progress >= 1) {
          if (outgoing && outgoing !== incoming) rig.remove(outgoing);
          setMaterialOpacity(incoming, 1);
          transition = null;
        }
      }
      if (currentModel) {
        if (!dragging && !reduceMotion.matches && now - idleSince > 1600) targetYaw += 0.0024;
        yaw += (targetYaw - yaw) * 0.09;
        pitch += (targetPitch - pitch) * 0.09;
        currentModel.rotation.y = yaw;
        currentModel.rotation.x = pitch;
      }
      renderer.render(scene, camera);
      requestNextFrame();
    };

    const stageObserver = new IntersectionObserver(([entry]) => {
      stageVisible = entry.isIntersecting;
      if (stageVisible) requestNextFrame();
      else if (animationFrame) {
        cancelAnimationFrame(animationFrame);
        animationFrame = null;
      }
    }, { rootMargin: '180px 0px', threshold: 0.01 });
    const syncDocumentVisibility = () => {
      if (document.hidden && animationFrame) {
        cancelAnimationFrame(animationFrame);
        animationFrame = null;
      } else {
        requestNextFrame();
      }
    };
    stageObserver.observe(stage);
    document.addEventListener('visibilitychange', syncDocumentVisibility);
    window.addEventListener('pagehide', () => {
      stageObserver.disconnect();
      document.removeEventListener('visibilitychange', syncDocumentVisibility);
      if (animationFrame) cancelAnimationFrame(animationFrame);
      renderer.dispose();
    }, { once: true });

    resize();
    showModel(0, { announce: false });
    requestNextFrame();
  }
}
