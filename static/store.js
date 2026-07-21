(() => {
    'use strict';

    const root = document.documentElement;
    const body = document.body;
    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const csrfToken = () => document.querySelector('[name="csrfmiddlewaretoken"]')?.value || '';
    const announce = message => {
        const region = document.getElementById('global-live-region');
        if (region) region.textContent = message;
    };
    const focusableSelector = 'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';
    const trapFocus = (event, container) => {
        if (event.key !== 'Tab' || !container) return;
        const items = [...container.querySelectorAll(focusableSelector)].filter(item => !item.hidden && item.offsetParent !== null);
        if (!items.length) {
            event.preventDefault();
            container.focus();
            return;
        }
        const first = items[0];
        const last = items[items.length - 1];
        if (event.shiftKey && document.activeElement === first) {
            event.preventDefault();
            last.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
            event.preventDefault();
            first.focus();
        }
    };

    // Complete persistent light/dark theme with system preference fallback.
    const themeButton = document.querySelector('.theme-toggle');
    const storedTheme = localStorage.getItem('nexora-theme');
    const initialTheme = storedTheme || (matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark');
    const setTheme = theme => {
        root.dataset.theme = theme;
        localStorage.setItem('nexora-theme', theme);
        themeButton?.setAttribute('aria-pressed', String(theme === 'light'));
        const label = theme === 'light' ? body.dataset.themeDarkLabel : body.dataset.themeLightLabel;
        themeButton?.setAttribute('title', label);
        themeButton?.setAttribute('aria-label', label);
        document.querySelector('meta[name="theme-color"]')?.setAttribute(
            'content', theme === 'light' ? 'oklch(97% .01 260)' : 'oklch(16% .03 264)'
        );
    };
    setTheme(initialTheme);
    themeButton?.addEventListener('click', () => setTheme(root.dataset.theme === 'dark' ? 'light' : 'dark'));

    // Responsive navigation.
    const navToggle = document.querySelector('.nav-toggle');
    const primaryNav = document.getElementById('primary-navigation');
    navToggle?.addEventListener('click', () => {
        const open = navToggle.getAttribute('aria-expanded') === 'true';
        navToggle.setAttribute('aria-expanded', String(!open));
        primaryNav?.classList.toggle('is-open', !open);
    });

    // Scroll progress and motion-safe reveal system.
    const progress = document.querySelector('.scroll-progress');
    let scrollFrame = 0;
    const updateProgress = () => {
        scrollFrame = 0;
        const maximum = document.documentElement.scrollHeight - innerHeight;
        const value = maximum > 0 ? scrollY / maximum : 0;
        progress?.style.setProperty('--scroll-progress', String(value));
    };
    addEventListener('scroll', () => {
        if (!scrollFrame) scrollFrame = requestAnimationFrame(updateProgress);
    }, { passive: true });
    updateProgress();

    const revealItems = document.querySelectorAll('.reveal, .product-card');
    if (reduceMotion || !('IntersectionObserver' in window)) {
        revealItems.forEach(item => item.classList.add('is-visible'));
    } else {
        const observer = new IntersectionObserver(entries => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    entry.target.classList.add('is-visible');
                    observer.unobserve(entry.target);
                }
            });
        }, { rootMargin: '0px 0px -8% 0px', threshold: 0.08 });
        revealItems.forEach(item => observer.observe(item));
    }

    if (!reduceMotion && matchMedia('(pointer: fine)').matches) {
        document.querySelectorAll('.tilt-card').forEach(card => {
            card.addEventListener('pointermove', event => {
                const rect = card.getBoundingClientRect();
                const x = (event.clientX - rect.left) / rect.width - 0.5;
                const y = (event.clientY - rect.top) / rect.height - 0.5;
                card.style.setProperty('--tilt-x', `${y * -3.5}deg`);
                card.style.setProperty('--tilt-y', `${x * 4.5}deg`);
            });
            card.addEventListener('pointerleave', () => {
                card.style.removeProperty('--tilt-x');
                card.style.removeProperty('--tilt-y');
            });
        });
    }

    document.querySelectorAll('.tech-video video').forEach(video => {
        const button = video.closest('.tech-video')?.querySelector('.video-toggle');
        if (reduceMotion) video.pause();
        button?.addEventListener('click', () => {
            if (video.paused) {
                video.play();
                button.setAttribute('aria-pressed', 'false');
                button.querySelector('span').textContent = button.dataset.pauseLabel;
            } else {
                video.pause();
                button.setAttribute('aria-pressed', 'true');
                button.querySelector('span').textContent = button.dataset.playLabel;
            }
        });
    });

    // Cart drawer: safe DOM construction, focus management, localized endpoints.
    const drawer = document.getElementById('cart-drawer');
    const overlay = document.querySelector('.drawer-overlay');
    const drawerItems = document.getElementById('cart-drawer-items');
    const cartOpeners = document.querySelectorAll('[data-cart-open]');
    const cartClosers = document.querySelectorAll('[data-cart-close]');
    let drawerTrigger = null;
    const drawerBackground = [document.querySelector('.site-header'), document.querySelector('main'), document.querySelector('.site-footer'), document.querySelector('.guide')].filter(Boolean);

    const create = (tag, className, text) => {
        const element = document.createElement(tag);
        if (className) element.className = className;
        if (text !== undefined) element.textContent = text;
        return element;
    };
    const endpointFor = (template, id) => template.replace(/\/0\/?$/, `/${id}/`);

    const renderCart = data => {
        if (!drawerItems) return;
        drawerItems.replaceChildren();
        const count = (data.items || []).reduce((total, item) => total + item.qty, 0);
        const countNode = document.getElementById('global-bag-count');
        if (countNode) countNode.textContent = String(count);
        if (!data.items?.length) {
            drawerItems.append(create('p', 'cart-empty', body.dataset.emptyLabel));
        }
        (data.items || []).forEach(item => {
            const row = create('article', 'cart-drawer-row');
            const imageLink = create('a', 'cart-drawer-image');
            imageLink.href = item.url;
            const image = document.createElement('img');
            image.src = item.image;
            image.alt = item.name;
            image.loading = 'lazy';
            image.addEventListener('error', () => {
                image.hidden = true;
                imageLink.classList.add('image-unavailable');
            }, { once: true });
            imageLink.append(image);
            const info = create('div', 'cart-drawer-info');
            const title = create('a', 'cart-drawer-title', item.name);
            title.href = item.url;
            info.append(title, create('span', 'cart-drawer-price', item.price));
            const controls = create('div', 'cart-quantity');
            const minus = create('button', 'quantity-button', '−');
            minus.type = 'button';
            minus.setAttribute('aria-label', `${body.dataset.quantityLabel}: ${item.name} −`);
            minus.addEventListener('click', () => updateCart(item.id, item.qty - 1, item.variant_id).catch(error => announce(error.message))); 
            const quantity = create('span', '', String(item.qty));
            quantity.setAttribute('aria-live', 'polite');
            const plus = create('button', 'quantity-button', '+');
            plus.type = 'button';
            plus.setAttribute('aria-label', `${body.dataset.quantityLabel}: ${item.name} +`);
            plus.addEventListener('click', () => updateCart(item.id, item.qty + 1, item.variant_id).catch(error => announce(error.message))); 
            controls.append(minus, quantity, plus);
            info.append(controls);
            row.append(imageLink, info, create('strong', 'cart-line-total', item.line_total));
            drawerItems.append(row);
        });
        const total = document.getElementById('cart-drawer-total');
        if (total) total.textContent = data.total;
    };

    const fetchCart = async () => {
        const response = await fetch(body.dataset.cartUrl, { headers: { Accept: 'application/json' } });
        if (!response.ok) throw new Error(body.dataset.cartLoadError);
        const data = await response.json();
        renderCart(data);
        return data;
    };
    const openCart = async trigger => {
        drawerTrigger = trigger;
        drawer?.classList.add('is-open');
        drawer?.setAttribute('aria-hidden', 'false');
        overlay.hidden = false;
        body.classList.add('drawer-open');
        drawerBackground.forEach(element => { element.inert = true; });
        cartOpeners.forEach(opener => opener.setAttribute('aria-expanded', 'true'));
        try { await fetchCart(); } catch (error) { announce(error.message); }
        drawer?.querySelector('button')?.focus();
    };
    const closeCart = () => {
        drawer?.classList.remove('is-open');
        drawer?.setAttribute('aria-hidden', 'true');
        overlay.hidden = true;
        body.classList.remove('drawer-open');
        drawerBackground.forEach(element => { element.inert = false; });
        cartOpeners.forEach(opener => opener.setAttribute('aria-expanded', 'false'));
        drawerTrigger?.focus();
    };
    cartOpeners.forEach(opener => opener.addEventListener('click', event => {
        event.preventDefault();
        openCart(opener);
    }));
    cartClosers.forEach(closer => closer.addEventListener('click', closeCart));

    const updateCart = async (id, quantity, variantId = null) => {
        const formData = new FormData();
        formData.append('quantity', quantity);
        if (variantId) formData.append('variant', variantId);
        const response = await fetch(endpointFor(body.dataset.cartUpdateTemplate, id), {
            method: 'POST', headers: { 'X-CSRFToken': csrfToken(), Accept: 'application/json' }, body: formData,
        });
        if (!response.ok) throw new Error(body.dataset.cartUpdateError);
        renderCart(await response.json());
    };

    document.addEventListener('submit', async event => {
        const form = event.target.closest('form[data-add-to-bag]');
        if (!form) return;
        event.preventDefault();
        const submit = form.querySelector('[type="submit"]');
        submit?.setAttribute('aria-busy', 'true');
        try {
            const response = await fetch(form.dataset.ajaxUrl, {
                method: 'POST', headers: { 'X-CSRFToken': csrfToken(), Accept: 'application/json' }, body: new FormData(form),
            });
            if (!response.ok) throw new Error(body.dataset.cartAddError);
            renderCart(await response.json());
            await openCart(submit || form);
            announce(body.dataset.productAdded);
        } catch (error) {
            announce(error.message);
            form.submit();
        } finally {
            submit?.removeAttribute('aria-busy');
        }
    });

    // Product options update the visible price, quantity limit and submitted cart variant.
    document.querySelectorAll('[data-variant-picker]').forEach(picker => {
        const form = picker.parentElement?.querySelector('form[data-add-to-bag]');
        const selectedInput = form?.querySelector('[data-selected-variant]');
        const quantityInput = form?.querySelector('[name="quantity"]');
        const price = picker.parentElement?.querySelector('.pdp-price');
        const currency = picker.dataset.currency || '';
        const buttons = [...picker.querySelectorAll('.variant-chip-btn:not([disabled])')];
        const selectVariant = button => {
            if (!button || button.disabled) return;
            buttons.forEach(option => {
                const selected = option === button;
                option.classList.toggle('is-selected', selected);
                option.setAttribute('aria-pressed', String(selected));
            });
            if (selectedInput) selectedInput.value = button.dataset.variantId;
            if (price) {
                const amount = Number(button.dataset.variantPrice || 0);
                price.textContent = `${new Intl.NumberFormat(undefined, { maximumFractionDigits: 0 }).format(amount)} ${currency}`.trim();
            }
            if (quantityInput) {
                const stock = Math.max(1, Number(button.dataset.variantStock || 1));
                quantityInput.max = String(stock);
                if (Number(quantityInput.value) > stock) quantityInput.value = String(stock);
            }
        };
        buttons.forEach(button => button.addEventListener('click', () => selectVariant(button)));
        selectVariant(buttons[0]);
    });

    // Accessible catalogue assistant with CSRF and safe text rendering.
    const guidePanel = document.getElementById('guide-panel');
    const guideOpen = document.querySelector('.guide-launch');
    const guideClose = document.querySelector('.guide-close');
    const guideForm = document.querySelector('.guide-form');
    const guideMessages = document.querySelector('.guide-messages');
    const setGuide = open => {
        guidePanel.hidden = !open;
        guideOpen?.setAttribute('aria-expanded', String(open));
        if (open) guidePanel.querySelector('input')?.focus();
        else guideOpen?.focus();
    };
    guideOpen?.addEventListener('click', () => setGuide(true));
    guideClose?.addEventListener('click', () => setGuide(false));
    guideForm?.addEventListener('submit', async event => {
        event.preventDefault();
        const input = guideForm.querySelector('#guide-question');
        const message = input.value.trim();
        if (!message) return;
        guideMessages.append(create('p', 'guide-user', message));
        input.value = '';
        guideForm.setAttribute('aria-busy', 'true');
        try {
            const response = await fetch(body.dataset.guideUrl, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken(), Accept: 'application/json' },
                body: JSON.stringify({ message }),
            });
            const data = await response.json();
            guideMessages.append(create('p', 'guide-bot', data.reply || body.dataset.guideUnable));
            (data.products || []).forEach(product => {
                const card = create('article', 'guide-product');
                const productImage = document.createElement('img');
                productImage.src = product.image;
                productImage.alt = product.name;
                productImage.loading = 'lazy';
                productImage.width = 72;
                productImage.height = 72;
                const link = create('a', '', product.name);
                link.href = product.url;
                const details = product.rating_count
                    ? `${product.brand} · ★ ${product.rating} · ${product.price} ₾`
                    : `${product.brand} · ${product.price} ₾`;
                card.append(productImage, link, create('small', '', details));
                guideMessages.append(card);
            });
        } catch (error) {
            guideMessages.append(create('p', 'guide-bot guide-error', body.dataset.connectionError));
        } finally {
            guideForm.removeAttribute('aria-busy');
            guideMessages.scrollTop = guideMessages.scrollHeight;
        }
    });

    // Gallery, accordions, and saved-address helpers.
    const galleryButtons = [...document.querySelectorAll('[data-gallery-src]')];
    const selectGalleryImage = button => {
        if (!button) return;
        const image = document.getElementById('main-product-image');
        if (image) {
            image.classList.remove('is-gallery-changing');
            void image.offsetWidth;
            image.classList.add('is-gallery-changing');
            image.src = button.dataset.gallerySrc;
            image.alt = button.dataset.galleryAlt || image.alt;
        }
        galleryButtons.forEach(item => item.setAttribute('aria-pressed', String(item === button)));
        const selectedIndex = galleryButtons.indexOf(button);
        const position = document.getElementById('gallery-position');
        if (position) position.textContent = String(selectedIndex + 1) + ' / ' + String(galleryButtons.length);
        const following = galleryButtons[(selectedIndex + 1) % galleryButtons.length];
        if (following?.dataset.gallerySrc) {
            const preload = new Image();
            preload.src = following.dataset.gallerySrc;
        }
    };
    galleryButtons.forEach(button => button.addEventListener('click', () => selectGalleryImage(button)));
    const stepGallery = direction => {
        if (!galleryButtons.length) return;
        const active = galleryButtons.findIndex(button => button.getAttribute('aria-pressed') === 'true');
        selectGalleryImage(galleryButtons[(Math.max(active, 0) + direction + galleryButtons.length) % galleryButtons.length]);
    };
    document.querySelectorAll('[data-gallery-prev]').forEach(button => button.addEventListener('click', () => stepGallery(-1)));
    document.querySelectorAll('[data-gallery-next]').forEach(button => button.addEventListener('click', () => stepGallery(1)));
    const gallery = document.querySelector('.pdp-gallery');
    let galleryTouchStart = null;
    gallery?.addEventListener('keydown', event => {
        if (galleryButtons.length < 2) return;
        if (event.key === 'ArrowRight' || event.key === 'ArrowDown') { event.preventDefault(); stepGallery(1); }
        if (event.key === 'ArrowLeft' || event.key === 'ArrowUp') { event.preventDefault(); stepGallery(-1); }
    });
    gallery?.addEventListener('touchstart', event => { galleryTouchStart = event.changedTouches[0].clientX; }, { passive: true });
    gallery?.addEventListener('touchend', event => {
        if (galleryTouchStart === null || galleryButtons.length < 2) return;
        const delta = event.changedTouches[0].clientX - galleryTouchStart;
        galleryTouchStart = null;
        if (Math.abs(delta) > 42) stepGallery(delta < 0 ? 1 : -1);
    }, { passive: true });
    document.querySelectorAll('.accordion-title').forEach(button => button.addEventListener('click', () => {
        const expanded = button.getAttribute('aria-expanded') === 'true';
        button.setAttribute('aria-expanded', String(!expanded));
        const panel = document.getElementById(button.getAttribute('aria-controls'));
        if (panel) panel.hidden = expanded;
    }));
    document.querySelectorAll('[data-address-fill]').forEach(button => button.addEventListener('click', () => {
        Object.entries(button.dataset).forEach(([key, value]) => {
            if (!key.startsWith('field')) return;
            const inputName = key.slice(5).replace(/^[A-Z]/, value => value.toLowerCase());
            const field = document.getElementById(`id_${inputName.replace(/[A-Z]/g, value => `_${value.toLowerCase()}`)}`);
            if (field) field.value = value;
        });
    }));

    addEventListener('keydown', event => {
        if (event.key === 'Tab' && drawer?.classList.contains('is-open')) {
            trapFocus(event, drawer);
            return;
        }
        if (event.key !== 'Escape') return;
        if (drawer?.classList.contains('is-open')) closeCart();
        else if (guidePanel && !guidePanel.hidden) setGuide(false);
    });
    const ratingForm = document.querySelector('[data-rating-form]');
    ratingForm?.addEventListener('submit', async event => {
        event.preventDefault();
        const selectedRating = ratingForm.querySelector('input[name=rating]:checked');
        if (!selectedRating) {
            ratingForm.reportValidity();
            return;
        }
        const submit = ratingForm.querySelector('[type=submit]');
        const controls = ratingForm.querySelectorAll('input,button');
        controls.forEach(control => { control.disabled = true; });
        submit?.setAttribute('aria-busy', 'true');
        const status = ratingForm.querySelector('[data-rating-status]');
        try {
            const response = await fetch(ratingForm.action, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken(),
                    'X-Requested-With': 'XMLHttpRequest',
                    Accept: 'application/json',
                },
                body: JSON.stringify({ rating: selectedRating.value }),
            });
            const data = await response.json();
            if (response.status === 401 && data.login_url) {
                location.assign(data.login_url);
                return;
            }
            if (!response.ok) throw new Error(data.error || body.dataset.connectionError);
            const average = document.querySelector('[data-rating-average]');
            const count = document.querySelector('[data-rating-count]');
            if (average) average.textContent = Number(data.average).toFixed(1);
            if (count) count.textContent = String(data.count);
            if (status) status.textContent = data.message;
            announce(data.message);
        } catch (error) {
            if (status) status.textContent = error.message;
            announce(error.message);
        } finally {
            controls.forEach(control => { control.disabled = false; });
            submit?.removeAttribute('aria-busy');
        }
    });
})();
document.querySelectorAll('[data-password-toggle]').forEach((toggle) => {
  const input = document.getElementById(toggle.getAttribute('aria-controls'));
  if (!input) return;
  const icon = toggle.querySelector('use');
  toggle.addEventListener('click', () => {
    const visible = input.type === 'password';
    input.type = visible ? 'text' : 'password';
    toggle.setAttribute('aria-pressed', String(visible));
    toggle.setAttribute('aria-label', visible ? 'Hide password' : 'Show password');
    if (icon) icon.setAttribute('href', visible ? '#icon-eye-off' : '#icon-eye');
  });
});
