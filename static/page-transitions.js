(() => {
    'use strict';

    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const transitionKey = 'nexora:page-transition';
    const transitionDuration = 180;
    const warmStart = sessionStorage.getItem(transitionKey) === '1';
    const body = document.body;

    if (warmStart) {
        body.dataset.pageTransition = 'warm';
        sessionStorage.removeItem(transitionKey);
        requestAnimationFrame(() => {
            window.setTimeout(() => {
                delete body.dataset.pageTransition;
            }, 460);
        });
    }

    if (reduceMotion) return;

    let navigating = false;

    const isPlainLeftClick = event => (
        event.button === 0 &&
        !event.metaKey &&
        !event.ctrlKey &&
        !event.shiftKey &&
        !event.altKey
    );

    const shouldSkipLink = link => {
        if (!link) return true;
        if (link.hasAttribute('download')) return true;
        if (link.dataset.cartOpen !== undefined) return true;
        if (link.closest('[data-no-page-transition]')) return true;
        const href = link.getAttribute('href') || '';
        if (!href || href.startsWith('#') || href.startsWith('mailto:') || href.startsWith('tel:') || href.startsWith('javascript:')) return true;
        if ((link.target || '').toLowerCase() && (link.target || '').toLowerCase() !== '_self') return true;
        if ((link.rel || '').split(/\s+/).includes('external')) return true;
        const url = new URL(link.href, window.location.href);
        if (url.origin !== window.location.origin) return true;
        if (url.pathname === window.location.pathname && url.search === window.location.search && url.hash) return true;
        return false;
    };

    const beginNavigation = href => {
        if (navigating) return;
        navigating = true;
        sessionStorage.setItem(transitionKey, '1');
        body.classList.add('is-page-transitioning');
        window.setTimeout(() => {
            window.location.assign(href);
        }, transitionDuration);
    };

    document.addEventListener('click', event => {
        if (event.defaultPrevented || !isPlainLeftClick(event)) return;
        const link = event.target.closest('a[href]');
        if (shouldSkipLink(link)) return;
        event.preventDefault();
        beginNavigation(link.href);
    }, true);
})();
