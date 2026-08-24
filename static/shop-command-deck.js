(() => {
  const search = document.querySelector('[data-command-search]');
  const sort = document.querySelector('[data-command-sort]');

  if (search) {
    search.addEventListener('submit', () => {
      search.classList.add('is-pending');
      search.setAttribute('aria-busy', 'true');
    });
  }

  if (!sort) return;

  sort.addEventListener('click', event => {
    const link = event.target.closest('a[href]');
    if (!link || event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;

    sort.classList.add('is-pending');
    sort.setAttribute('aria-busy', 'true');
    link.classList.add('is-pending');
  });
})();
