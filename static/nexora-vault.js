(() => {
  'use strict';

  const chamber = document.querySelector('[data-signal-chamber]');
  if (!chamber) return;

  const stage = chamber.querySelector('[data-signal-stage]');
  const objects = [...chamber.querySelectorAll('[data-signal-object]')];
  const details = [...chamber.querySelectorAll('[data-signal-detail]')];
  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
  const canParallax = window.matchMedia('(hover: hover) and (pointer: fine)').matches;

  const selectObject = object => {
    if (!object) return;
    const target = object.dataset.signalTarget;
    objects.forEach(item => {
      const active = item === object;
      item.classList.toggle('is-active', active);
      item.setAttribute('aria-pressed', String(active));
    });
    details.forEach(detail => {
      const active = detail.id === target;
      detail.hidden = !active;
      detail.classList.toggle('is-active', active);
    });
  };

  objects.forEach((object, index) => {
    object.addEventListener('click', () => selectObject(object));
    object.addEventListener('keydown', event => {
      if (event.key !== 'ArrowRight' && event.key !== 'ArrowLeft') return;
      event.preventDefault();
      const nextIndex = (index + (event.key === 'ArrowRight' ? 1 : -1) + objects.length) % objects.length;
      selectObject(objects[nextIndex]);
      objects[nextIndex].focus({ preventScroll: true });
    });
  });

  if (stage && canParallax && !reducedMotion.matches) {
    stage.addEventListener('pointermove', event => {
      const bounds = stage.getBoundingClientRect();
      const x = (event.clientX - bounds.left) / bounds.width - .5;
      const y = (event.clientY - bounds.top) / bounds.height - .5;
      objects.forEach((object, index) => {
        const depth = 1 + index * .35;
        object.style.setProperty('--object-x', `${x * 20 * depth}px`);
        object.style.setProperty('--object-y', `${y * 13 * depth}px`);
      });
    });
    stage.addEventListener('pointerleave', () => objects.forEach(object => {
      object.style.removeProperty('--object-x');
      object.style.removeProperty('--object-y');
    }));
  }
})();
