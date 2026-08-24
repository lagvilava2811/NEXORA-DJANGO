(() => {
  const root = document.querySelector('[data-editions]');
  if (!root) return;
  const cards = [...root.querySelectorAll('[data-edition]')];
  const dots = [...root.querySelectorAll('[data-editions-dot]')];
  const previous = root.querySelector('[data-editions-prev]');
  const next = root.querySelector('[data-editions-next]');
  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  let active = 0;
  let timer;
  const show = (target, focus = false) => {
    active = (target + cards.length) % cards.length;
    cards.forEach((card, index) => {
      const selected = index === active;
      card.classList.toggle('is-active', selected);
      card.setAttribute('aria-hidden', String(!selected));
    });
    dots.forEach((dot, index) => {
      const selected = index === active;
      dot.classList.toggle('is-active', selected);
      dot.setAttribute('aria-selected', String(selected));
      if (focus && selected) dot.focus();
    });
  };
  const restart = () => {
    window.clearInterval(timer);
    if (!reduced) timer = window.setInterval(() => show(active + 1), 6200);
  };
  previous.addEventListener('click', () => { show(active - 1, true); restart(); });
  next.addEventListener('click', () => { show(active + 1, true); restart(); });
  dots.forEach((dot, index) => dot.addEventListener('click', () => { show(index, true); restart(); }));
  root.addEventListener('mouseenter', () => window.clearInterval(timer));
  root.addEventListener('mouseleave', restart);
  root.addEventListener('focusin', () => window.clearInterval(timer));
  root.addEventListener('focusout', (event) => { if (!root.contains(event.relatedTarget)) restart(); });
  restart();
})();
