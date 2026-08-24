(() => {
  const root = document.querySelector('[data-signup-lamp]');
  const control = root?.querySelector('[data-lamp-toggle]');
  if (!root || !control) return;

  let startY = null;
  let suppressClick = false;
  const setLamp = on => {
    root.classList.toggle('is-lamp-on', on);
    control.setAttribute('aria-pressed', String(on));
  };
  const toggleLamp = () => setLamp(!root.classList.contains('is-lamp-on'));

  root.classList.add('signup-lamp-enhanced');
  setLamp(root.dataset.formErrors === 'true');

  control.addEventListener('click', () => {
    if (suppressClick) {
      suppressClick = false;
      return;
    }
    toggleLamp();
  });
  control.addEventListener('pointerdown', event => {
    startY = event.clientY;
    control.setPointerCapture?.(event.pointerId);
  });
  control.addEventListener('pointerup', event => {
    if (startY !== null && event.clientY - startY > 18) {
      suppressClick = true;
      toggleLamp();
    }
    startY = null;
  });
  control.addEventListener('pointercancel', () => { startY = null; });
})();
