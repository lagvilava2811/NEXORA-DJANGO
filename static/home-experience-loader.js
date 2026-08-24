(() => {
  const root = document.querySelector('[data-home-experience]');
  if (!root) return;

  const { gsapUrl, heroModuleUrl, morphModuleUrl } = root.dataset;
  if (!gsapUrl || !heroModuleUrl || !morphModuleUrl) return;

  let loadingPromise = null;

  const loadClassicScript = (url) => new Promise((resolve, reject) => {
    if (window.gsap) {
      resolve();
      return;
    }
    const existing = [...document.scripts].find((item) => item.dataset.lazySrc === url);
    if (existing) {
      existing.addEventListener('load', resolve, { once: true });
      existing.addEventListener('error', reject, { once: true });
      return;
    }
    const script = document.createElement('script');
    script.src = url;
    script.async = true;
    script.dataset.lazySrc = url;
    script.addEventListener('load', resolve, { once: true });
    script.addEventListener('error', reject, { once: true });
    document.head.append(script);
  });

  const loadExperience = () => {
    if (loadingPromise) return loadingPromise;
    root.classList.add('is-experience-loading');
    loadingPromise = loadClassicScript(gsapUrl)
      .then(() => Promise.all([import(heroModuleUrl), import(morphModuleUrl)]))
      .then(() => {
        root.classList.remove('is-experience-loading');
        root.classList.add('is-experience-ready');
        return true;
      })
      .catch((error) => {
        loadingPromise = null;
        root.classList.remove('is-experience-loading');
        root.classList.add('has-experience-error');
        console.error('NEXORA 3D experience failed to load', error);
        return false;
      });
    return loadingPromise;
  };

  const scheduleLoad = () => {
    if ('requestIdleCallback' in window) {
      window.requestIdleCallback(loadExperience, { timeout: 900 });
    } else {
      window.setTimeout(loadExperience, 120);
    }
  };

  const observer = 'IntersectionObserver' in window
    ? new IntersectionObserver((entries) => {
      if (!entries.some((entry) => entry.isIntersecting)) return;
      observer.disconnect();
      scheduleLoad();
    }, { rootMargin: '420px 0px' })
    : null;

  if (observer) observer.observe(root);
  else scheduleLoad();

  root.addEventListener('pointerenter', loadExperience, { once: true, passive: true });
  root.addEventListener('focusin', loadExperience, { once: true });
  root.addEventListener('click', (event) => {
    const control = event.target.closest('[data-experience-dock] button, [data-morph-select]');
    if (!control || root.classList.contains('is-experience-ready')) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    loadExperience().then((loaded) => {
      if (loaded) control.click();
    });
  }, { capture: true });
})();
