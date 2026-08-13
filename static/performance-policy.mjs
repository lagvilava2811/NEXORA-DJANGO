export function experiencePolicy({
  reducedMotion = false,
  saveData = false,
  effectiveType = '',
  viewportWidth,
  deviceMemory,
  hardwareConcurrency,
} = {}) {
  if (reducedMotion) {
    return { tier: 'static', webgl: false, ambientVideo: false };
  }

  const slowConnection = effectiveType === 'slow-2g' || effectiveType === '2g';
  const smallViewport = Number.isFinite(viewportWidth) && viewportWidth < 768;
  const constrainedMemory = Number.isFinite(deviceMemory) && deviceMemory <= 4;
  const constrainedCpu = Number.isFinite(hardwareConcurrency) && hardwareConcurrency <= 4;
  if (saveData || slowConnection || smallViewport || constrainedMemory || constrainedCpu) {
    return { tier: 'lite', webgl: false, ambientVideo: false };
  }

  return { tier: 'full', webgl: true, ambientVideo: true };
}

export function browserExperiencePolicy() {
  const connection = navigator.connection || navigator.mozConnection || navigator.webkitConnection;
  return experiencePolicy({
    reducedMotion: window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false,
    saveData: connection?.saveData ?? false,
    effectiveType: connection?.effectiveType ?? '',
    viewportWidth: window.innerWidth,
    deviceMemory: navigator.deviceMemory,
    hardwareConcurrency: navigator.hardwareConcurrency,
  });
}
