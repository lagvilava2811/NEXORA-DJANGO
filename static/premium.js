(() => {
  const header = document.querySelector('[data-site-header]');
  if (header && 'IntersectionObserver' in window) {
    const sentinel = document.createElement('div');
    sentinel.setAttribute('aria-hidden', 'true');
    sentinel.style.cssText = 'position:absolute;inset:0 auto auto 0;width:1px;height:1px;pointer-events:none;';
    document.body.prepend(sentinel);
    new IntersectionObserver(([entry]) => {
      header.classList.toggle('is-scrolled', !entry.isIntersecting);
    }, { threshold: 0 }).observe(sentinel);
  }

  const dock = document.querySelector('[data-experience-dock]');
  const guide = document.getElementById('guide-panel');
  const drawer = document.getElementById('cart-drawer');
  if (dock && (guide || drawer)) {
    const syncDock = () => {
      const guideOpen = guide && !guide.hidden;
      const drawerOpen = drawer && drawer.classList.contains('is-open');
      dock.classList.toggle('is-dimmed', Boolean(guideOpen || drawerOpen));
    };
    new MutationObserver(syncDock).observe(document.body, {
      subtree: true,
      attributes: true,
      attributeFilter: ['class', 'hidden', 'aria-hidden'],
    });
    syncDock();
  }

  // Motion is deliberately opt-in: without JavaScript every section stays visible.
  // We use a single observer and only composite-friendly properties.
  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (!reducedMotion && 'IntersectionObserver' in window) {
    const revealGroups = [
      '.precision-film',
      '.precision-drop',
      '.precision-arrivals',
      '.precision-signal',
      '.commerce-shop-head',
      '.commerce-filter-rail',
      '.commerce-pdp-gallery',
      '.pdp-info-panel',
      '.related-products-section',
      '.product-rating-card',
    ];
    const staggerGroups = [
      '.precision-product-grid .product-card',
      '.commerce-product-grid .product-card',
      '.related-products-section .product-card',
    ];
    const targets = new Set();
    revealGroups.forEach(selector => document.querySelectorAll(selector).forEach(node => {
      node.classList.add('reveal');
      targets.add(node);
    }));
    staggerGroups.forEach(selector => document.querySelectorAll(selector).forEach((node, index) => {
      node.classList.add('reveal', 'reveal-stagger');
      node.style.setProperty('--reveal-delay', `${Math.min(index % 8, 7) * 52}ms`);
      targets.add(node);
    }));
    if (targets.size) {
      document.documentElement.classList.add('motion-ready');
      const revealObserver = new IntersectionObserver(entries => {
        entries.forEach(entry => {
          if (!entry.isIntersecting) return;
          entry.target.classList.add('is-revealed');
          revealObserver.unobserve(entry.target);
        });
      }, { rootMargin: '0px 0px -8% 0px', threshold: 0.08 });
      targets.forEach(target => revealObserver.observe(target));
    }
  }

  document.querySelectorAll('.product-image img, .main-image-container > img').forEach(image => {
    image.addEventListener('error', () => image.closest('.product-image, .main-image-container')?.classList.add('media-load-error'), { once: true });
  });

  const mainImage = document.getElementById('main-product-image');
  if (mainImage) {
    const stage = mainImage.closest('.main-image-container');
    if (stage) {
      stage.tabIndex = 0;
      stage.setAttribute('role', 'button');
      stage.setAttribute('aria-label', mainImage.alt);
      const openZoom = () => {
        const dialog = document.createElement('dialog');
        dialog.className = 'premium-media-dialog';
        dialog.setAttribute('aria-label', mainImage.alt);
        const close = document.createElement('button');
        close.type = 'button';
        close.className = 'premium-media-close';
        close.textContent = document.body.dataset.closeLabel || 'Close';
        close.addEventListener('click', () => dialog.close());
        const image = document.createElement('img');
        image.src = mainImage.currentSrc || mainImage.src;
        image.alt = mainImage.alt;
        dialog.append(close, image);
        dialog.addEventListener('close', () => dialog.remove(), { once: true });
        document.body.append(dialog);
        dialog.showModal();
      };
      stage.addEventListener('click', openZoom);
      stage.addEventListener('keydown', event => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault();
          openZoom();
        }
      });

      // A detail lens is deliberately desktop-only: touch users retain the
      // accessible full-screen dialog, and reduced-motion users get no hover
      // treatment at all. The lens always reads the currently selected image.
      const canMagnify = window.matchMedia('(hover: hover) and (pointer: fine) and (prefers-reduced-motion: no-preference)');
      let lens;
      const removeLens = () => {
        lens?.remove();
        lens = undefined;
        stage.classList.remove('has-magnifier');
      };
      const updateLens = event => {
        if (!canMagnify.matches || !mainImage.complete || !mainImage.naturalWidth) return;
        if (!lens) {
          lens = document.createElement('span');
          lens.className = 'premium-image-lens';
          lens.setAttribute('aria-hidden', 'true');
          stage.append(lens);
          stage.classList.add('has-magnifier');
        }
        const bounds = stage.getBoundingClientRect();
        const x = Math.max(0, Math.min(event.clientX - bounds.left, bounds.width));
        const y = Math.max(0, Math.min(event.clientY - bounds.top, bounds.height));
        const source = mainImage.currentSrc || mainImage.src;
        lens.style.backgroundImage = `url("${source}")`;
        lens.style.backgroundSize = '260%';
        lens.style.backgroundPosition = `${(x / bounds.width) * 100}% ${(y / bounds.height) * 100}%`;
        lens.style.setProperty('--lens-x', `${x}px`);
        lens.style.setProperty('--lens-y', `${y}px`);
      };
      stage.addEventListener('pointermove', updateLens);
      stage.addEventListener('pointerleave', removeLens);
      stage.addEventListener('keydown', event => {
        if (event.key === 'Escape') removeLens();
      });
      canMagnify.addEventListener?.('change', event => {
        if (!event.matches) removeLens();
      });
    }
  }

  // On narrow screens filters are a proper modal drawer rather than a long,
  // always-open rail. Links and forms retain their normal Django GET behavior.
  const filterToggle = document.querySelector('[data-filter-toggle]');
  const filterDrawer = document.querySelector('[data-filter-drawer]');
  const filterClose = document.querySelector('[data-filter-close]');
  const filterScrim = document.querySelector('[data-filter-scrim]');
  if (filterToggle && filterDrawer && filterScrim) {
    const narrowViewport = window.matchMedia('(max-width: 65rem)');
    let restoreFocus = false;
    const closeFilters = ({ focusToggle = false } = {}) => {
      filterDrawer.classList.remove('is-open');
      filterToggle.setAttribute('aria-expanded', 'false');
      filterScrim.hidden = true;
      document.body.classList.remove('filter-drawer-open');
      if (focusToggle && restoreFocus) filterToggle.focus();
      restoreFocus = false;
    };
    const openFilters = () => {
      if (!narrowViewport.matches) return;
      restoreFocus = document.activeElement === filterToggle;
      filterDrawer.classList.add('is-open');
      filterToggle.setAttribute('aria-expanded', 'true');
      filterScrim.hidden = false;
      document.body.classList.add('filter-drawer-open');
      filterDrawer.focus({ preventScroll: true });
    };
    filterToggle.addEventListener('click', () => {
      if (filterDrawer.classList.contains('is-open')) closeFilters({ focusToggle: true });
      else openFilters();
    });
    filterClose?.addEventListener('click', () => closeFilters({ focusToggle: true }));
    filterScrim.addEventListener('click', () => closeFilters({ focusToggle: true }));
    document.addEventListener('keydown', event => {
      if (event.key === 'Escape' && filterDrawer.classList.contains('is-open')) {
        event.preventDefault();
        closeFilters({ focusToggle: true });
      }
    });
    narrowViewport.addEventListener?.('change', event => {
      if (!event.matches) closeFilters();
    });
  }
  const audioCopy = document.getElementById('premium-audio-copy');
  if (audioCopy) {
    const { play, signal, volume, track, ready, chooseTrack, motion, featured } = audioCopy.dataset;
    const playButton = document.querySelector('.hero3d-play');
    const trackName = document.querySelector('[data-track-name]');
    const volumeControl = document.querySelector('.hero3d-volume');
    const trackGroup = document.querySelector('.hero3d-tracks');
    const audioState = document.querySelector('[data-audio-state]');
    if (playButton) playButton.setAttribute('aria-label', play);
    if (trackName) trackName.textContent = signal;
    if (volumeControl) volumeControl.setAttribute('aria-label', volume);
    if (trackGroup) trackGroup.setAttribute('aria-label', chooseTrack);
    if (audioState) audioState.textContent = ready;
    document.querySelectorAll('.hero3d-track').forEach((button, index) => button.setAttribute('aria-label', `${track} ${index + 1}`));
    document.querySelector('.tech-video-copy .hero-kicker')?.replaceChildren(motion);
    document.querySelector('.precision-drop-copy .hero-kicker')?.replaceChildren(featured);
  }

  const sortLabel = document.querySelector('[data-sort-label]')?.textContent?.trim();
  if (sortLabel) document.querySelector('.sort-controls')?.setAttribute('aria-label', sortLabel);
})();
