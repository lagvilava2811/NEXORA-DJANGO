(() => {
  const stage = document.querySelector('[data-catalog-stage]');
  if (!stage) return;

  const cards = [...stage.querySelectorAll('.catalog-stage-card')];
  if (!cards.length) return;

  const interactive = window.matchMedia('(hover: hover) and (pointer: fine) and (prefers-reduced-motion: no-preference)').matches;
  if (!interactive) return;

  const reset = () => {
    cards.forEach(card => {
      card.style.setProperty('--card-shift-x', '0px');
      card.style.setProperty('--card-shift-y', '0px');
      card.style.setProperty('--card-rotate-x', '0deg');
      card.style.setProperty('--card-rotate-y', '0deg');
    });
  };

  stage.addEventListener('pointermove', event => {
    const bounds = stage.getBoundingClientRect();
    const x = ((event.clientX - bounds.left) / bounds.width - 0.5) * 2;
    const y = ((event.clientY - bounds.top) / bounds.height - 0.5) * 2;

    cards.forEach((card, index) => {
      const depth = ((index % 5) + 1) / 5;
      card.style.setProperty('--card-shift-x', `${x * 22 * depth}px`);
      card.style.setProperty('--card-shift-y', `${y * 14 * depth}px`);
      card.style.setProperty('--card-rotate-x', `${y * -5.5 * depth}deg`);
      card.style.setProperty('--card-rotate-y', `${x * 7 * depth}deg`);
    });
  });

  stage.addEventListener('pointerleave', reset);
  stage.addEventListener('blur', reset, true);
})();
