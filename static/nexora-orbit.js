(() => {
  'use strict';

  const orbit = document.querySelector('[data-nexora-orbit]');
  if (!orbit) return;

  const stage = orbit.querySelector('[data-orbit-stage]');
  const cards = [...orbit.querySelectorAll('[data-orbit-card]')];
  const previous = orbit.querySelector('[data-orbit-prev]');
  const next = orbit.querySelector('[data-orbit-next]');
  const status = orbit.querySelector('[data-orbit-status]');
  const positionLabel = orbit.dataset.positionLabel || 'Product';
  const frontLabel = orbit.dataset.frontLabel || 'Front view';
  const detailsLabel = orbit.dataset.detailsLabel || 'Details revealed';
  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
  const compactCarousel = window.matchMedia('(max-width: 58rem)');
  let active = 0;
  let dragStart = null;
  let suppressClick = false;

  if (!stage || cards.length < 1) return;

  const productName = card => card.querySelector('.nexora-orbit-card-identity strong, .nexora-orbit-card-back h2')?.textContent.trim() || 'Product';
  const setStatus = () => {
    const card = cards[active];
    if (!status || !card) return;
    status.textContent = `${productName(card)}. ${positionLabel} ${active + 1} / ${cards.length}. ${card.classList.contains('is-flipped') ? detailsLabel : frontLabel}.`;
  };
  const render = ({ instant = false } = {}) => {
    const angle = 360 / cards.length;
    const radius = Math.min(Math.max(stage.clientWidth * .34, 130), 250);
    cards.forEach((card, index) => {
      const offset = (index - active + cards.length) % cards.length;
      const signedOffset = offset > cards.length / 2 ? offset - cards.length : offset;
      const radians = signedOffset * angle * Math.PI / 180;
      const x = Math.sin(radians) * radius;
      const z = Math.cos(radians) * radius - radius;
      const y = Math.abs(signedOffset) * 10;
      card.style.setProperty('--orbit-x', `${x}px`);
      card.style.setProperty('--orbit-y', `${y}px`);
      card.style.setProperty('--orbit-z', `${z}px`);
      card.style.setProperty('--orbit-rotate', `${-signedOffset * angle * .38}deg`);
      card.style.zIndex = String(20 - Math.round(Math.abs(signedOffset)));
      card.classList.toggle('is-active', index === active);
      // Compact mode deliberately presents only the active product plus its
      // immediate neighbors. This is recomputed from the current state, so
      // an active product can never become one of the hidden cards.
      card.classList.toggle('is-mobile-hidden', compactCarousel.matches && Math.abs(signedOffset) > 1);
      card.setAttribute('aria-current', index === active ? 'true' : 'false');
      card.setAttribute(
        'aria-label',
        `${productName(card)}. ${positionLabel} ${index + 1} / ${cards.length}. ${card.classList.contains('is-flipped') ? detailsLabel : frontLabel}.`,
      );
      if (instant || reduceMotion.matches) card.style.transitionDuration = '0ms';
      else card.style.removeProperty('transition-duration');
    });
    setStatus();
  };
  const rotate = direction => {
    cards[active]?.classList.remove('is-flipped');
    active = (active + direction + cards.length) % cards.length;
    render();
  };
  const select = index => {
    if (index === active) {
      cards[active].classList.toggle('is-flipped');
      setStatus();
      return;
    }
    cards[active]?.classList.remove('is-flipped');
    active = index;
    render();
  };

  previous?.addEventListener('click', () => rotate(-1));
  next?.addEventListener('click', () => rotate(1));
  cards.forEach((card, index) => {
    card.addEventListener('click', event => {
      if (suppressClick || event.target.closest('a')) return;
      select(index);
    });
    card.addEventListener('keydown', event => {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        select(index);
      } else if (event.key === 'ArrowRight') {
        event.preventDefault();
        rotate(1);
        cards[active].focus({ preventScroll: true });
      } else if (event.key === 'ArrowLeft') {
        event.preventDefault();
        rotate(-1);
        cards[active].focus({ preventScroll: true });
      }
    });
  });

  stage.addEventListener('pointerdown', event => {
    dragStart = { x: event.clientX, y: event.clientY };
    suppressClick = false;
    stage.setPointerCapture?.(event.pointerId);
  });
  stage.addEventListener('pointerup', event => {
    if (!dragStart) return;
    const deltaX = event.clientX - dragStart.x;
    const deltaY = event.clientY - dragStart.y;
    dragStart = null;
    if (Math.abs(deltaX) > 36 && Math.abs(deltaX) > Math.abs(deltaY)) {
      suppressClick = true;
      rotate(deltaX < 0 ? 1 : -1);
      window.setTimeout(() => { suppressClick = false; }, 0);
    }
  });
  stage.addEventListener('pointercancel', () => { dragStart = null; });
  window.addEventListener('resize', () => render({ instant: true }), { passive: true });
  reduceMotion.addEventListener?.('change', () => render({ instant: true }));
  compactCarousel.addEventListener?.('change', () => render({ instant: true }));
  render({ instant: true });
})();
