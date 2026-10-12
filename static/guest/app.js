(function () {
    const API_BASE = '..';

    function escapeHtml(s) {
        const div = document.createElement('div');
        div.textContent = s || '';
        return div.innerHTML;
    }

    // В исходных данных иногда остаются ярлыки-заголовки вроде "Описание:\xa0"
    // или "Ингредиенты:"/"Состав:" (а то и просто осиротевшее ":"), скопированные
    // из таблицы при заполнении меню. Для гостей это выглядит неряшливо — срезаем.
    function stripLabel(text, label) {
        if (!text) return text;
        const re = new RegExp(`^\\s*(?:(?:${label})\\s*:\\s*)?:?\\s*`, 'iu');
        return text.replace(re, '').trim();
    }

    function cleanDescription(raw) {
        if (!raw) return '';
        let desc = stripLabel(raw, 'Описание');
        const dupIdx = desc.search(/\n*\s*Состав\s*:/i);
        if (dupIdx !== -1) desc = desc.slice(0, dupIdx).trim();
        return desc;
    }

    function cleanIngredients(raw) {
        return stripLabel(raw, 'Ингредиенты|Состав');
    }

    function formatPrice(n) {
        return Math.round(n).toString().replace(/\B(?=(\d{3})+(?!\d))/g, '.');
    }

    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    function photoInnerHtml(item, alt) {
        if (item.photo_url) {
            return `<img src="${item.photo_url}" alt="${escapeHtml(alt)}" loading="lazy">`;
        }
        return `<span class="item-photo-placeholder">🍵</span>`;
    }

    // Карточки появляются «пачкой» при прокрутке — каждая со своей задержкой.
    const cardObserver = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (!entry.isIntersecting) return;
            entry.target.classList.add('shown');
            cardObserver.unobserve(entry.target);
        });
    }, { rootMargin: '0px 0px -8% 0px', threshold: 0.05 });

    const sectionObserver = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) entry.target.classList.add('in-view');
        });
    }, { threshold: 0.08 });

    function renderItemCard(item, index, columns) {
        const card = document.createElement('div');
        card.className = 'item-card';
        card.style.setProperty('--i', index % columns);
        card.setAttribute('role', 'button');
        card.setAttribute('tabindex', '0');

        card.innerHTML = `
            ${item.is_hit ? '<div class="hit-badge">Хит 🔥</div>' : ''}
            <div class="item-photo">${photoInnerHtml(item, item.name)}</div>
            <div class="item-card-body">
                <div class="item-card-name">${escapeHtml(item.name)}</div>
                ${item.calories ? `<span class="item-card-kcal">${item.calories} ккал</span>` : ''}
                <div class="item-card-foot">
                    ${item.price ? `<span class="item-card-price">${formatPrice(item.price)}</span>` : '<span></span>'}
                    <span class="item-card-plus" aria-hidden="true">+</span>
                </div>
            </div>
        `;
        card.onclick = () => openDishModal(item, card);
        card.onkeydown = (e) => {
            if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); openDishModal(item, card); }
        };
        cardObserver.observe(card);
        return card;
    }

    // Секции по очереди окрашиваются в фирменные цвета — как листы, наползающие друг на друга.
    const THEMES = ['theme-cream', 'theme-indigo', 'theme-matcha', 'theme-lilac', 'theme-deep'];

    function renderMenu(categories) {
        const root = document.getElementById('menu-root');
        const navInner = document.getElementById('cat-nav-inner');
        root.innerHTML = '';
        navInner.querySelectorAll('.cat-chip').forEach(c => c.remove());

        // Некоторые позиции сняты с публичной витрины (hidden_from_guest), но
        // остаются в боте для сотрудников — гостям их показывать не нужно.
        const visible = (items) => items.filter(it => !it.hidden_from_guest);
        const columns = window.innerWidth >= 560 ? 3 : 2;

        const order = ['kitchen', 'bar'];
        const grouped = order.map(t => ({ type: t, cats: categories.filter(c => c.type === t) }))
            .filter(g => g.cats.length > 0);

        let sectionIndex = 0;
        grouped.forEach(group => {
            group.cats.forEach(cat => {
                const items = visible(cat.items);
                if (items.length === 0) return;

                const chip = document.createElement('button');
                chip.className = 'cat-chip';
                chip.textContent = cat.name;
                chip.dataset.target = `cat-${cat.id}`;
                chip.onclick = () => {
                    document.getElementById(`cat-${cat.id}`).scrollIntoView({ behavior: 'smooth', block: 'start' });
                };
                navInner.appendChild(chip);

                const section = document.createElement('section');
                section.className = `menu-section ${THEMES[sectionIndex % THEMES.length]}`;
                section.id = `cat-${cat.id}`;
                section.style.zIndex = sectionIndex + 1;
                sectionIndex++;

                const ghost = document.createElement('div');
                ghost.className = 'section-ghost';
                ghost.setAttribute('aria-hidden', 'true');
                ghost.textContent = `${cat.name} · ${cat.name} · ${cat.name} · ${cat.name}`;
                section.appendChild(ghost);

                const inner = document.createElement('div');
                inner.className = 'section-inner';

                const head = document.createElement('div');
                head.className = 'menu-section-head';
                head.innerHTML = `<div class="head-mask"><h2 class="head-line">${escapeHtml(cat.name)}</h2></div><span class="count">${items.length}</span>`;
                inner.appendChild(head);

                const grid = document.createElement('div');
                grid.className = 'item-grid';
                items.forEach((item, i) => grid.appendChild(renderItemCard(item, i, columns)));
                inner.appendChild(grid);

                section.appendChild(inner);
                root.appendChild(section);
                sectionObserver.observe(section);
            });
        });

        setupActiveChipTracking();
        onScroll();
    }

    function moveIndicator(chip) {
        const indicator = document.getElementById('cat-indicator');
        if (!indicator || !chip) return;
        indicator.style.width = `${chip.offsetWidth}px`;
        indicator.style.transform = `translateX(${chip.offsetLeft}px)`;
    }

    function setupActiveChipTracking() {
        const sections = Array.from(document.querySelectorAll('.menu-section'));
        const chips = Array.from(document.querySelectorAll('.cat-chip'));
        if (!sections.length) return;

        let currentId = null;
        const setActive = (id) => {
            if (id === currentId) return;
            currentId = id;
            chips.forEach(c => c.classList.toggle('active', c.dataset.target === id));
            const activeChip = chips.find(c => c.dataset.target === id);
            moveIndicator(activeChip);
            if (activeChip) {
                const nav = document.getElementById('cat-nav-inner');
                nav.scrollTo({ left: activeChip.offsetLeft - (nav.clientWidth - activeChip.offsetWidth) / 2, behavior: 'smooth' });
            }
        };

        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) setActive(entry.target.id);
            });
        }, { rootMargin: '-120px 0px -70% 0px', threshold: 0 });

        sections.forEach(s => observer.observe(s));
        setActive(sections[0].id);
        window.addEventListener('resize', () => moveIndicator(chips.find(c => c.classList.contains('active'))));
    }

    // Прокрутка: сжимаем шапку, двигаем «призрачные» заголовки секций и фоновые пятна.
    let ticking = false;
    function onScroll() {
        if (ticking) return;
        ticking = true;
        requestAnimationFrame(() => {
            ticking = false;
            const y = window.scrollY;
            document.getElementById('site-header').classList.toggle('scrolled', y > 10);
            if (reduceMotion) return;
            const vh = window.innerHeight;
            document.querySelectorAll('.section-ghost').forEach((ghost, i) => {
                const rect = ghost.parentElement.getBoundingClientRect();
                if (rect.bottom < 0 || rect.top > vh) return;
                const shift = (vh - rect.top) * 0.35;
                ghost.style.transform = `translateX(${i % 2 ? shift - 400 : -shift}px)`;
            });
            document.querySelectorAll('.blob').forEach((blob, i) => {
                blob.style.transform = `translateY(${-y * (0.08 + i * 0.05)}px)`;
            });
        });
    }
    window.addEventListener('scroll', onScroll, { passive: true });

    function ringHtml(cls, value, label, ratio, suffix) {
        const len = 188.5; // 2πr при r = 30
        const offset = len * (1 - Math.max(0, Math.min(1, ratio)));
        return `
            <div class="kbzhu-ring ${cls}">
                <div class="ring-wrap">
                    <svg viewBox="0 0 72 72"><circle class="track" cx="36" cy="36" r="30"/><circle class="bar" cx="36" cy="36" r="30" data-offset="${offset}"/></svg>
                    <span class="ring-val" data-count="${value}">0${suffix}</span>
                </div>
                <div class="ring-label">${label}</div>
            </div>`;
    }

    function animateKbzhu(root) {
        root.querySelectorAll('.bar').forEach(bar => {
            requestAnimationFrame(() => requestAnimationFrame(() => { bar.style.strokeDashoffset = bar.dataset.offset; }));
        });
        root.querySelectorAll('.ring-val').forEach(el => {
            const target = parseFloat(el.dataset.count) || 0;
            const suffix = el.textContent.replace(/^[\d.,]+/, '');
            const isInt = Number.isInteger(target);
            if (reduceMotion) { el.textContent = target + suffix; return; }
            const start = performance.now() + 350;
            const dur = 1000;
            const tick = (now) => {
                const t = Math.max(0, Math.min(1, (now - start) / dur));
                const eased = 1 - Math.pow(1 - t, 3);
                const v = target * eased;
                el.textContent = (isInt ? Math.round(v) : v.toFixed(1)) + suffix;
                if (t < 1) requestAnimationFrame(tick);
            };
            requestAnimationFrame(tick);
        });
    }

    // Фото «перелетает» из карточки в шапку открытой карточки блюда.
    function flyPhoto(fromImg, toBox) {
        if (reduceMotion || !fromImg || !fromImg.complete || !fromImg.naturalWidth) return;
        const from = fromImg.getBoundingClientRect();
        const to = toBox.getBoundingClientRect();
        const clone = document.createElement('img');
        clone.src = fromImg.currentSrc || fromImg.src;
        clone.className = 'fly-photo';
        Object.assign(clone.style, { left: `${to.left}px`, top: `${to.top}px`, width: `${to.width}px`, height: `${to.height}px` });
        document.body.appendChild(clone);
        toBox.classList.add('hide-img');

        const sx = from.width / to.width;
        const sy = from.height / to.height;
        const anim = clone.animate([
            { transform: `translate(${from.left - to.left}px, ${from.top - to.top}px) scale(${sx}, ${sy})`, transformOrigin: 'top left', borderRadius: '22px' },
            { transform: 'none', transformOrigin: 'top left', borderRadius: '0px' }
        ], { duration: 520, easing: 'cubic-bezier(0.22, 1, 0.36, 1)' });
        anim.onfinish = () => {
            toBox.classList.remove('hide-img');
            clone.remove();
        };
    }

    function openDishModal(item, card) {
        const modal = document.getElementById('dish-modal');
        const sheet = document.getElementById('dish-modal-sheet');
        sheet.scrollTop = 0;
        sheet.style.removeProperty('--drag');

        const photoBox = document.getElementById('dish-modal-photo');
        photoBox.innerHTML = photoInnerHtml(item, item.name);
        const img = photoBox.querySelector('img');
        if (img) img.loading = 'eager';

        document.getElementById('dish-modal-name').textContent = item.name;
        document.getElementById('dish-modal-volume').textContent = item.volume || '';

        const priceEl = document.getElementById('dish-modal-price');
        priceEl.textContent = item.price ? `${formatPrice(item.price)} сум` : '';
        priceEl.style.display = item.price ? '' : 'none';

        const noteEl = document.getElementById('dish-modal-price-note');
        noteEl.textContent = item.price_note || '';
        noteEl.style.display = item.price_note ? '' : 'none';

        const desc = cleanDescription(item.description);
        const descEl = document.getElementById('dish-modal-desc');
        descEl.textContent = desc;
        descEl.style.display = desc ? '' : 'none';

        const kbzhuEl = document.getElementById('dish-modal-kbzhu');
        if (item.calories) {
            const p = Number(item.protein) || 0;
            const f = Number(item.fat) || 0;
            const c = Number(item.carbs) || 0;
            const macroMax = Math.max(p, f, c, 1);
            kbzhuEl.innerHTML =
                ringHtml('kcal', Number(item.calories) || 0, 'ккал', Math.min(1, (Number(item.calories) || 0) / 800), '') +
                ringHtml('p', p, 'белки', p / macroMax, 'г') +
                ringHtml('f', f, 'жиры', f / macroMax, 'г') +
                ringHtml('c', c, 'углев.', c / macroMax, 'г');
            kbzhuEl.style.display = '';
        } else {
            kbzhuEl.innerHTML = '';
            kbzhuEl.style.display = 'none';
        }

        const ingr = cleanIngredients(item.ingredients);
        const ingrEl = document.getElementById('dish-modal-ingredients');
        ingrEl.innerHTML = ingr ? `<b>Состав</b>${escapeHtml(ingr)}` : '';
        ingrEl.style.display = ingr ? '' : 'none';

        const allergensEl = document.getElementById('dish-modal-allergens');
        allergensEl.textContent = item.allergens ? `⚠️ Аллергены: ${item.allergens}` : '';

        // Перезапускаем каскадную анимацию содержимого при каждом открытии.
        modal.classList.remove('open');
        void modal.offsetWidth;
        modal.classList.add('open');
        document.body.style.overflow = 'hidden';

        if (card && window.innerWidth < 560) flyPhoto(card.querySelector('.item-photo img'), photoBox);
        if (item.calories) animateKbzhu(kbzhuEl);
    }

    function closeDishModal() {
        const modal = document.getElementById('dish-modal');
        if (!modal.classList.contains('open')) return;
        modal.classList.remove('open');
        document.getElementById('dish-modal-sheet').style.removeProperty('--drag');
        document.body.style.overflow = '';
    }

    document.getElementById('dish-modal-close').onclick = closeDishModal;
    document.querySelector('.dish-modal-backdrop').onclick = closeDishModal;
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') closeDishModal();
    });

    // Смахивание карточки блюда вниз, как в нативных приложениях.
    (function setupSwipeToClose() {
        const sheet = document.getElementById('dish-modal-sheet');
        let startY = null;
        let dy = 0;
        sheet.addEventListener('touchstart', (e) => {
            if (sheet.scrollTop > 0) { startY = null; return; }
            startY = e.touches[0].clientY;
            dy = 0;
        }, { passive: true });
        sheet.addEventListener('touchmove', (e) => {
            if (startY === null) return;
            dy = e.touches[0].clientY - startY;
            if (dy <= 0) { sheet.classList.remove('dragging'); sheet.style.removeProperty('--drag'); return; }
            sheet.classList.add('dragging');
            sheet.style.setProperty('--drag', `${dy}px`);
        }, { passive: true });
        sheet.addEventListener('touchend', () => {
            if (startY === null) return;
            sheet.classList.remove('dragging');
            if (dy > 110) closeDishModal();
            else sheet.style.removeProperty('--drag');
            startY = null;
        });
    })();

    // Разбиваем «МЕНЮ» на буквы для анимации появления.
    document.querySelectorAll('[data-split]').forEach(el => {
        const text = el.textContent;
        el.innerHTML = Array.from(text).map((ch, i) => `<span class="ch" style="--ci:${i}">${escapeHtml(ch)}</span>`).join('');
    });

    // Заставка показывается один раз за визит.
    (function runSplash() {
        const splash = document.getElementById('splash');
        let seen = false;
        try { seen = sessionStorage.getItem('mc_splash') === '1'; } catch (e) { /* приватный режим */ }
        const finish = () => {
            splash.classList.add('done');
            document.body.classList.remove('is-loading');
            document.body.classList.add('ready');
            try { sessionStorage.setItem('mc_splash', '1'); } catch (e) { /* приватный режим */ }
            setTimeout(() => splash.remove(), 900);
        };
        if (seen || reduceMotion) {
            splash.remove();
            document.body.classList.remove('is-loading');
            document.body.classList.add('ready');
            return;
        }
        setTimeout(finish, 1500);
    })();

    async function loadMenu() {
        try {
            const res = await fetch(`${API_BASE}/api/menu`);
            const data = await res.json();
            renderMenu(data.categories || []);
        } catch (e) {
            console.error('Menu load error:', e);
            document.getElementById('menu-root').innerHTML =
                '<p style="text-align:center;color:#ef4444;padding:40px 0;">Не удалось загрузить меню. Попробуйте обновить страницу.</p>';
        }
    }

    async function loadFact() {
        try {
            const res = await fetch(`${API_BASE}/api/facts/random`);
            const data = await res.json();
            if (data && data.text) {
                document.getElementById('fact-text').textContent = data.text;
                document.getElementById('fact-card').classList.remove('hidden');
            }
        } catch (e) {
            console.error('Fact load error:', e);
        }
    }

    async function loadBranches() {
        try {
            const res = await fetch(`${API_BASE}/api/branches`);
            const data = await res.json();

            const philEl = document.getElementById('philosophy-text');
            if (data.philosophy && philEl) {
                philEl.textContent = data.philosophy;
                document.getElementById('philosophy-card').classList.remove('hidden');
            }

            const allergyEl = document.getElementById('allergy-note');
            if (data.allergy_note && allergyEl) {
                allergyEl.textContent = '⚠️ ' + data.allergy_note;
            }

            const igEl = document.getElementById('instagram-link');
            if (data.instagram && igEl) {
                const handle = data.instagram.replace(/^@/, '');
                igEl.href = `https://instagram.com/${handle}`;
                igEl.textContent = data.instagram;
                igEl.classList.remove('hidden');
            }

            const list = document.getElementById('branches-list');
            if (list && Array.isArray(data.branches)) {
                list.innerHTML = '';
                data.branches.forEach(b => {
                    const row = document.createElement('div');
                    row.className = 'branch-row';
                    const telHref = b.phone ? `tel:${b.phone}` : '#';
                    const telDisplay = b.phone ? b.phone.replace('+998', '+998 ').replace(/(\d{2})(\d{3})(\d{2})(\d{2})$/, '$1 $2 $3 $4') : '';
                    row.innerHTML = `
                        <div class="branch-name">${escapeHtml(b.name)}</div>
                        <div class="branch-address">${escapeHtml(b.address || '')}</div>
                        ${b.phone ? `<a class="branch-phone" href="${telHref}">${escapeHtml(telDisplay)}</a>` : ''}
                    `;
                    list.appendChild(row);
                });
            }
        } catch (e) {
            console.error('Branches load error:', e);
        }
    }

    loadMenu();
    loadFact();
    loadBranches();
})();
