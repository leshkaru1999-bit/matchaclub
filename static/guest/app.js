(function () {
    const API_BASE = '..';
    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    // Ролики для баннера. match — по какому названию категории искать раздел,
    // к которому ведёт нажатие на подпись; type — запасной вариант (кухня/бар).
    const SLIDES = [
        { v: 'latte', title: 'Матча-латте', sub: 'фирменный напиток Matcha Club', match: /матч|латте|напит/i, type: 'bar' },
        { v: 'breakfast', title: 'Завтраки', sub: 'смотреть меню', match: /завтрак/i, type: 'kitchen' },
        { v: 'dessert', title: 'Десерты', sub: 'к матче — самое то', match: /десерт|сладк/i, type: 'kitchen' },
        { v: 'ceremony', title: 'Матча', sub: 'взбиваем венчиком часэн', match: /матч/i, type: 'bar' },
        { v: 'sandwich', title: 'Сэндвичи', sub: 'собираем вручную', match: /сэндвич|сендвич|тост/i, type: 'kitchen' },
        { v: 'roll', title: 'Боулы и салаты', sub: 'зелень, овощи и белок', match: /боул|салат|ролл/i, type: 'kitchen' },
    ];
    const SLIDE_MS = 6500;

    // Цены, которых нет в меню на сервере (блюдо не попало в печатное меню,
    // откуда цены переносились). Срабатывает, только если цена в боте не задана —
    // как только её поставят через «💰 Цена», возьмётся она.
    const PRICE_FALLBACK = {
        'авокадо-тост с яйцом пашот и халуми': 115000,
    };
    const normName = (n) => (n || '').toLowerCase().replace(/ё/g, 'е').replace(/[.\s]+$/, '').trim();

    const GROUP_LABELS = { foryou: 'для тебя', kitchen: 'еда', bar: 'напитки' };

    function escapeHtml(s) {
        const div = document.createElement('div');
        div.textContent = s == null ? '' : String(s);
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
        return Math.round(n).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ' ') + ' сум';
    }

    // В боте объём часто записан просто числом («300»). Гостю непонятно, что
    // это, поэтому дописываем единицу: для бара — мл, для кухни — граммы.
    function formatVolume(item) {
        const v = (item.volume || '').toString().trim();
        if (/^\d+(?:[.,]\d+)?$/.test(v)) return `${v}\u00A0${item._type === 'bar' ? 'мл' : 'г'}`;
        return v;
    }

    const CHEV = '<svg class="chev" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 6l6 6-6 6"/></svg>';

    function photoHtml(item, eager, extra) {
        const inner = item.photo_url
            ? `<img src="${escapeHtml(item.photo_url)}" alt="${escapeHtml(item.name)}" ${eager ? '' : 'loading="lazy"'} decoding="async">`
            : '<span class="ph-empty">🍵</span>';
        return `<div class="ph">${inner}${extra || ''}</div>`;
    }

    // Фото проявляются, когда реально загрузились, а не «выскакивают» по кускам.
    function wirePhotos(root) {
        root.querySelectorAll('.ph img').forEach(img => {
            const done = () => img.classList.add('loaded');
            if (img.complete && img.naturalWidth) done();
            else { img.addEventListener('load', done, { once: true }); img.addEventListener('error', done, { once: true }); }
        });
    }

    const riseObserver = 'IntersectionObserver' in window ? new IntersectionObserver((entries) => {
        entries.forEach(e => {
            if (!e.isIntersecting) return;
            e.target.classList.add('in');
            riseObserver.unobserve(e.target);
        });
    }, { rootMargin: '0px 0px -6% 0px' }) : null;

    function rise(el, delay) {
        el.classList.add('rise');
        el.style.setProperty('--d', delay || 0);
        if (riseObserver && !reduceMotion) riseObserver.observe(el);
        else el.classList.add('in');
        return el;
    }

    // ─── Карточки ───
    function miniCard(item) {
        const b = document.createElement('button');
        b.type = 'button';
        b.className = 'mini';
        b.innerHTML = `
            ${photoHtml(item)}
            <span class="mini-name">${escapeHtml(item.name)}</span>
            <span class="price-row">${item.price ? `<span class="price">${formatPrice(item.price)}</span>` : '<span></span>'}${CHEV}</span>`;
        b.onclick = () => openDish(item, b.querySelector('.ph'));
        return b;
    }

    function posterCard(item) {
        const b = document.createElement('button');
        b.type = 'button';
        b.className = 'poster';
        b.innerHTML = `
            ${photoHtml(item)}
            <span class="poster-body">
                <span class="poster-name">${escapeHtml(item.name)}</span>
                <span class="poster-foot">
                    <span class="poster-price">${item.price ? formatPrice(item.price) : ''}</span>
                    <span class="poster-go">${CHEV.replace('class="chev"', '')}</span>
                </span>
            </span>`;
        b.onclick = () => openDish(item, b);
        return b;
    }

    function gridCard(item, wide) {
        const b = document.createElement('button');
        b.type = 'button';
        b.className = 'card' + (wide ? ' wide' : '');
        const meta = [formatVolume(item), item.calories ? `${item.calories} ккал` : ''].filter(Boolean).join(' · ');
        const text = `
            <span class="card-name">${escapeHtml(item.name)}</span>
            ${meta ? `<span class="card-meta">${escapeHtml(meta)}</span>` : ''}
            <span class="card-foot price-row">${item.price ? `<span class="price">${formatPrice(item.price)}</span>` : '<span></span>'}${CHEV}</span>`;
        b.innerHTML = photoHtml(item, false, item.is_hit ? '<span class="hit">хит</span>' : '')
            + (wide ? `<span class="card-body">${text}</span>` : text);
        const ph = b.querySelector('.ph');
        b.onclick = () => openDish(item, ph);
        return b;
    }

    // ─── Меню ───
    let sections = [];   // { id, group, title, el }
    let factText = '';

    function makeSection(id, group, title) {
        const s = document.createElement('section');
        s.className = 'section';
        s.id = id;
        s.dataset.group = group;
        if (title) {
            const h = document.createElement('h2');
            h.className = 'section-title';
            h.textContent = title;
            s.appendChild(rise(h));
        }
        sections.push({ id, group, title: title || '', el: s });
        return s;
    }

    function renderMenu(categories) {
        const root = document.getElementById('menu-root');
        root.innerHTML = '';
        sections = [];

        // Некоторые позиции сняты с публичной витрины (hidden_from_guest), но
        // остаются в боте для сотрудников — гостям их показывать не нужно.
        const cats = categories
            .map(c => ({ ...c, items: (c.items || []).filter(it => !it.hidden_from_guest).map(it => ({
                ...it,
                _type: c.type,
                price: it.price || PRICE_FALLBACK[normName(it.name)] || it.price,
            })) }))
            .filter(c => c.items.length > 0);
        const order = ['kitchen', 'bar'];
        const ordered = order.flatMap(t => cats.filter(c => c.type === t))
            .concat(cats.filter(c => !order.includes(c.type)));
        const all = ordered.flatMap(c => c.items);
        const withPhoto = all.filter(it => it.photo_url);

        // «Для тебя»: хиты лентой, факт дня и подборка крупных обложек.
        let popular = all.filter(it => it.is_hit);
        if (popular.length < 4) popular = popular.concat(withPhoto.filter(it => !popular.includes(it))).slice(0, 8);
        if (popular.length) {
            const s = makeSection('s-popular', 'foryou', 'популярное');
            const rail = document.createElement('div');
            rail.className = 'rail';
            popular.slice(0, 10).forEach((it, i) => rail.appendChild(rise(miniCard(it), i)));
            s.appendChild(rail);
            root.appendChild(s);
        }

        const factSection = makeSection('s-fact', 'foryou', '');
        factSection.innerHTML = `
            <div class="promo">
                <div class="promo-label">знаете ли вы?</div>
                <div class="promo-text" id="fact-text">${escapeHtml(factText || 'Матча — это весь чайный лист, перетёртый в порошок: вы выпиваете его целиком.')}</div>
                <div class="promo-art" aria-hidden="true">🍵</div>
            </div>`;
        rise(factSection.firstElementChild);
        root.appendChild(factSection);

        const posters = withPhoto.filter(it => !popular.includes(it));
        const picks = (posters.length >= 3 ? posters : withPhoto).filter((_, i) => i % 2 === 0).slice(0, 8);
        if (picks.length) {
            const s = makeSection('s-try', 'foryou', 'попробуйте');
            const rail = document.createElement('div');
            rail.className = 'rail';
            picks.forEach((it, i) => rail.appendChild(rise(posterCard(it), i)));
            s.appendChild(rail);
            root.appendChild(s);
        }

        ordered.forEach(cat => {
            const s = makeSection(`cat-${cat.id}`, cat.type in GROUP_LABELS ? cat.type : 'kitchen', cat.name);
            s.dataset.catName = cat.name;
            const grid = document.createElement('div');
            grid.className = 'grid';
            const wideFirst = cat.items.length % 2 === 1 && cat.items.length > 1;
            cat.items.forEach((it, i) => grid.appendChild(rise(gridCard(it, wideFirst && i === 0), i % 2)));
            s.appendChild(grid);
            root.appendChild(s);
        });

        wirePhotos(root);
        buildTabs();
    }

    // ─── Вкладки: группы сверху, разделы группы снизу ───
    let currentGroup = null;
    let currentSection = null;
    let programmaticScroll = 0;

    function groupsInOrder() {
        const seen = [];
        sections.forEach(s => { if (!seen.includes(s.group)) seen.push(s.group); });
        return seen;
    }

    function buildTabs() {
        const main = document.getElementById('tabs-main');
        main.innerHTML = '';
        groupsInOrder().forEach(g => {
            const b = document.createElement('button');
            b.type = 'button';
            b.className = 'tab-main';
            b.dataset.group = g;
            b.textContent = GROUP_LABELS[g] || g;
            b.onclick = () => {
                const first = sections.find(s => s.group === g);
                if (first) scrollToSection(first.id);
            };
            main.appendChild(b);
        });
        updateActive(true);
    }

    function renderSubTabs(group) {
        const sub = document.getElementById('tabs-sub');
        sub.innerHTML = '';
        sections.filter(s => s.group === group && s.title).forEach(s => {
            const b = document.createElement('button');
            b.type = 'button';
            b.className = 'tab-sub';
            b.dataset.target = s.id;
            b.textContent = s.title.toLowerCase();
            b.onclick = () => scrollToSection(s.id);
            sub.appendChild(b);
        });
        sub.classList.remove('fade');
        void sub.offsetWidth;
        sub.classList.add('fade');
    }

    function scrollToSection(id) {
        const el = document.getElementById(id);
        if (!el) return;
        const tabsH = document.getElementById('tabs').offsetHeight;
        programmaticScroll = Date.now();
        window.scrollTo({ top: el.getBoundingClientRect().top + window.scrollY - tabsH + 4, behavior: reduceMotion ? 'auto' : 'smooth' });
        setActive(sections.find(s => s.id === id));
    }

    function centerInRow(row, el) {
        if (!el) return;
        row.scrollTo({ left: el.offsetLeft - (row.clientWidth - el.offsetWidth) / 2, behavior: 'smooth' });
    }

    function setActive(sec) {
        if (!sec) return;
        if (sec.group !== currentGroup) {
            currentGroup = sec.group;
            document.querySelectorAll('.tab-main').forEach(t => t.classList.toggle('active', t.dataset.group === currentGroup));
            centerInRow(document.getElementById('tabs-main'), document.querySelector(`.tab-main[data-group="${currentGroup}"]`));
            renderSubTabs(currentGroup);
            currentSection = null;
        }
        // Факт-плашка без заголовка подсвечивает предыдущий раздел группы.
        let target = sec;
        if (!target.title) {
            const idx = sections.indexOf(sec);
            for (let i = idx; i >= 0; i--) if (sections[i].title && sections[i].group === sec.group) { target = sections[i]; break; }
        }
        if (target.id !== currentSection) {
            currentSection = target.id;
            const subs = document.querySelectorAll('.tab-sub');
            subs.forEach(t => t.classList.toggle('active', t.dataset.target === currentSection));
            centerInRow(document.getElementById('tabs-sub'), document.querySelector(`.tab-sub[data-target="${currentSection}"]`));
        }
    }

    function updateActive(force) {
        if (!sections.length) return;
        if (!force && Date.now() - programmaticScroll < 700) return;
        const line = document.getElementById('tabs').offsetHeight + 24;
        let sec = sections[0];
        for (const s of sections) {
            if (s.el.getBoundingClientRect().top - line <= 0) sec = s;
            else break;
        }
        setActive(sec);
    }

    // ─── Прокрутка: параллакс баннера и «прилипшие» вкладки ───
    let ticking = false;
    function onScroll() {
        if (ticking) return;
        ticking = true;
        requestAnimationFrame(() => {
            ticking = false;
            const y = window.scrollY;
            const hero = document.getElementById('hero');
            const h = hero.offsetHeight;
            if (!reduceMotion && y < h) {
                document.getElementById('hero-media').style.transform = `translateY(${y * 0.35}px) scale(${1 + y / h * 0.08})`;
                const cap = document.getElementById('hero-caption');
                cap.style.transform = `translateY(${y * 0.15}px)`;
                cap.style.opacity = String(Math.max(0, 1 - y / (h * 0.45)));
            }
            document.getElementById('tabs').classList.toggle('stuck', y > h - 4);
            if (y > h && heroTimer) pauseHero(true);
            else if (y <= h && heroPaused) pauseHero(false);
            updateActive();
        });
    }
    window.addEventListener('scroll', onScroll, { passive: true });

    // ─── Видео-баннер ───
    let heroIndex = -1;
    let heroTimer = null;
    let heroStart = 0;
    let heroPaused = false;
    let heroElapsed = 0;
    const slideEls = [];

    function buildHero() {
        const media = document.getElementById('hero-media');
        const progress = document.getElementById('hero-progress');
        SLIDES.forEach((s, i) => {
            const el = document.createElement('div');
            el.className = 'hero-slide';
            el.innerHTML = `<img src="media/${s.v}.jpg" alt="" ${i ? 'loading="lazy"' : ''}>`;
            media.appendChild(el);
            slideEls.push(el);
            progress.appendChild(document.createElement('i'));
        });
        showSlide(0);

        // Свайп по баннеру листает ролики.
        let x0 = null;
        const hero = document.getElementById('hero');
        hero.addEventListener('touchstart', e => { x0 = e.touches[0].clientX; }, { passive: true });
        hero.addEventListener('touchend', e => {
            if (x0 === null) return;
            const dx = e.changedTouches[0].clientX - x0;
            x0 = null;
            if (Math.abs(dx) > 50) showSlide(heroIndex + (dx < 0 ? 1 : -1));
        });
        document.getElementById('hero-caption').onclick = () => {
            const s = SLIDES[heroIndex];
            const sec = sections.find(x => x.title && s.match.test(x.title) && x.group !== 'foryou')
                || sections.find(x => x.group === s.type);
            if (sec) scrollToSection(sec.id);
        };
    }

    function ensureVideo(i) {
        const el = slideEls[(i + SLIDES.length) % SLIDES.length];
        if (reduceMotion || el.querySelector('video')) return el.querySelector('video');
        const v = document.createElement('video');
        v.muted = true;
        v.defaultMuted = true;
        v.playsInline = true;
        v.setAttribute('playsinline', '');
        v.setAttribute('muted', '');
        v.loop = true;
        v.preload = 'auto';
        v.poster = `media/${SLIDES[(i + SLIDES.length) % SLIDES.length].v}.jpg`;
        v.src = `media/${SLIDES[(i + SLIDES.length) % SLIDES.length].v}.mp4`;
        el.appendChild(v);
        return v;
    }

    function showSlide(i) {
        i = (i + SLIDES.length) % SLIDES.length;
        if (i === heroIndex) return;
        const prev = slideEls[heroIndex];
        heroIndex = i;
        slideEls.forEach((el, k) => el.classList.toggle('active', k === i));
        if (prev) setTimeout(() => { const v = prev.querySelector('video'); if (v && !prev.classList.contains('active')) v.pause(); }, 900);
        const v = ensureVideo(i);
        if (v) { try { v.currentTime = 0; } catch (e) { /* ещё не загружено */ } const p = v.play(); if (p) p.catch(() => {}); }
        ensureVideo(i + 1); // подгружаем следующий заранее

        const s = SLIDES[i];
        const cap = document.getElementById('hero-caption');
        document.getElementById('hero-title').textContent = s.title;
        document.getElementById('hero-sub').textContent = s.sub + ' →';
        cap.classList.remove('swap');
        void cap.offsetWidth;
        cap.classList.add('swap');

        document.querySelectorAll('.hero-progress i').forEach((bar, k) => bar.style.setProperty('--p', k < i ? 1 : 0));
        heroElapsed = 0;
        heroStart = performance.now();
        if (!heroTimer && !heroPaused) heroTimer = requestAnimationFrame(tickHero);
    }

    function tickHero(now) {
        heroTimer = null;
        if (heroPaused) return;
        const t = heroElapsed + (now - heroStart);
        const bar = document.querySelectorAll('.hero-progress i')[heroIndex];
        if (bar) bar.style.setProperty('--p', Math.min(1, t / SLIDE_MS));
        if (t >= SLIDE_MS) { showSlide(heroIndex + 1); return; }
        heroTimer = requestAnimationFrame(tickHero);
    }

    function pauseHero(pause) {
        const v = slideEls[heroIndex] && slideEls[heroIndex].querySelector('video');
        if (pause) {
            heroPaused = true;
            heroElapsed += performance.now() - heroStart;
            if (heroTimer) cancelAnimationFrame(heroTimer);
            heroTimer = null;
            if (v) v.pause();
        } else {
            heroPaused = false;
            heroStart = performance.now();
            if (v) { const p = v.play(); if (p) p.catch(() => {}); }
            heroTimer = requestAnimationFrame(tickHero);
        }
    }
    document.addEventListener('visibilitychange', () => pauseHero(document.hidden || window.scrollY > document.getElementById('hero').offsetHeight));

    // ─── Карточка блюда ───
    const dish = document.getElementById('dish');
    let dishOrigin = null;

    function rectInset(el) {
        const r = el.getBoundingClientRect();
        const W = window.innerWidth, H = window.innerHeight;
        return `inset(${Math.max(0, r.top)}px ${Math.max(0, W - r.right)}px ${Math.max(0, H - r.bottom)}px ${Math.max(0, r.left)}px round 20px)`;
    }

    function openDish(item, originEl) {
        dishOrigin = originEl;
        document.getElementById('dish-bg').innerHTML = item.photo_url
            ? `<img class="blur" src="${escapeHtml(item.photo_url)}" alt=""><img class="main" src="${escapeHtml(item.photo_url)}" alt="${escapeHtml(item.name)}">`
            : '<span class="ph-empty">🍵</span>';
        document.getElementById('dish-name').textContent = item.name;

        const k = document.getElementById('dish-kbzhu');
        if (item.calories) {
            const cell = (v, l) => `<div class="fx" style="--d:${l[1]}"><b>${escapeHtml(v)}</b><span>${l[0]}</span></div>`;
            k.innerHTML = cell(item.calories, ['ккал', 1]) + cell(`${item.fat ?? 0} г`, ['жиры', 2])
                + cell(`${item.carbs ?? 0} г`, ['углеводы', 3]) + cell(`${item.protein ?? 0} г`, ['белки', 4]);
            k.hidden = false;
        } else {
            k.innerHTML = '';
            k.hidden = true;
        }

        const desc = cleanDescription(item.description);
        const ingr = cleanIngredients(item.ingredients);
        document.getElementById('dish-desc').textContent = desc;
        document.getElementById('dish-ingredients').innerHTML = ingr ? `<b>Состав:</b> ${escapeHtml(ingr)}` : '';
        document.getElementById('dish-allergens').textContent = item.allergens ? `Аллергены: ${item.allergens}` : '';
        document.getElementById('dish-price-note').textContent = item.price_note || '';
        const hasMore = !!(desc || ingr || item.allergens || item.price_note);
        const moreBtn = document.getElementById('dish-more-btn');
        moreBtn.hidden = !hasMore;
        moreBtn.setAttribute('aria-expanded', 'false');
        document.getElementById('dish-more').classList.remove('open');

        document.getElementById('dish-volume').textContent = formatVolume(item);
        document.getElementById('dish-price').textContent = item.price ? formatPrice(item.price) : '';

        // Порядок появления: название, КБЖУ, кнопка, нижняя плашка.
        document.getElementById('dish-name').className = 'dish-name fx';
        document.querySelector('.dish-bar').classList.add('fx');
        document.querySelector('.dish-bar').style.setProperty('--d', 6);

        dish.hidden = false;
        dish.classList.remove('shown');
        dish.style.transform = '';
        document.body.classList.add('dish-open');
        if (!history.state || !history.state.dish) history.pushState({ dish: true }, '');

        // Фото «раскрывается» из карточки на весь экран.
        if (!reduceMotion && originEl && dish.animate) {
            dish.animate([{ clipPath: rectInset(originEl) }, { clipPath: 'inset(0px 0px 0px 0px round 0px)' }],
                { duration: 520, easing: 'cubic-bezier(0.22, 1, 0.36, 1)' });
            document.getElementById('dish-bg').animate([{ transform: 'scale(1.15)' }, { transform: 'scale(1)' }],
                { duration: 700, easing: 'cubic-bezier(0.22, 1, 0.36, 1)' });
        }
        requestAnimationFrame(() => requestAnimationFrame(() => dish.classList.add('shown')));
        pauseHero(true);
    }

    function closeDish(fromHistory) {
        if (dish.hidden) return;
        const finish = () => {
            dish.hidden = true;
            dish.style.transform = '';
            document.body.classList.remove('dish-open');
            if (window.scrollY <= document.getElementById('hero').offsetHeight) pauseHero(false);
        };
        dish.classList.remove('shown');
        const r = dishOrigin && dishOrigin.getBoundingClientRect();
        const visible = r && r.bottom > 0 && r.top < window.innerHeight;
        if (!reduceMotion && dish.animate) {
            const anim = visible && !dish.style.transform
                ? dish.animate([{ clipPath: 'inset(0px 0px 0px 0px round 0px)' }, { clipPath: rectInset(dishOrigin) }],
                    { duration: 380, easing: 'cubic-bezier(0.4, 0, 0.2, 1)' })
                : dish.animate([{ transform: dish.style.transform || 'none', opacity: 1 }, { transform: 'translateY(100%)', opacity: 1 }],
                    { duration: 320, easing: 'cubic-bezier(0.4, 0, 1, 1)' });
            anim.onfinish = finish;
        } else finish();
        if (!fromHistory && history.state && history.state.dish) history.back();
    }

    document.getElementById('dish-close').onclick = () => closeDish();
    document.getElementById('dish-more-btn').onclick = (e) => {
        const btn = e.currentTarget;
        const open = btn.getAttribute('aria-expanded') !== 'true';
        btn.setAttribute('aria-expanded', String(open));
        document.getElementById('dish-more').classList.toggle('open', open);
    };
    document.addEventListener('keydown', e => { if (e.key === 'Escape') closeDish(); });
    // Кнопка «назад» на Android закрывает карточку, а не уводит со страницы.
    window.addEventListener('popstate', () => closeDish(true));

    // Смахивание карточки вниз.
    (function swipeToClose() {
        let y0 = null, dy = 0;
        const head = dish.querySelector('.dish-head');
        dish.addEventListener('touchstart', e => {
            const card = dish.querySelector('.dish-more-card');
            if ((head.contains(e.target) && head.scrollTop > 0) || (card.contains(e.target) && card.scrollTop > 0)) { y0 = null; return; }
            y0 = e.touches[0].clientY; dy = 0;
        }, { passive: true });
        dish.addEventListener('touchmove', e => {
            if (y0 === null) return;
            dy = Math.max(0, e.touches[0].clientY - y0);
            dish.style.transform = dy ? `translateY(${dy}px)` : '';
            dish.style.borderRadius = dy ? '28px 28px 0 0' : '';
        }, { passive: true });
        dish.addEventListener('touchend', () => {
            if (y0 === null) return;
            y0 = null;
            dish.style.borderRadius = '';
            if (dy > 120) closeDish();
            else if (dy) {
                dish.animate([{ transform: dish.style.transform }, { transform: 'none' }], { duration: 300, easing: 'cubic-bezier(0.34, 1.4, 0.64, 1)' });
                dish.style.transform = '';
            }
        });
    })();

    // ─── Данные ───
    async function loadMenu() {
        try {
            const res = await fetch(`${API_BASE}/api/menu`);
            const data = await res.json();
            renderMenu(data.categories || []);
        } catch (e) {
            console.error('Menu load error:', e);
            document.getElementById('menu-root').innerHTML =
                '<p style="text-align:center;color:#c2410c;padding:48px 16px;">Не удалось загрузить меню. Попробуйте обновить страницу.</p>';
        }
    }

    async function loadFact() {
        try {
            const res = await fetch(`${API_BASE}/api/facts/random`);
            const data = await res.json();
            if (data && data.text && data.text !== 'Факты не найдены') {
                factText = data.text;
                const el = document.getElementById('fact-text');
                if (el) el.textContent = data.text;
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
            if (data.philosophy) {
                philEl.textContent = data.philosophy;
                philEl.classList.remove('hidden');
            }
            const allergyEl = document.getElementById('allergy-note');
            if (data.allergy_note) {
                allergyEl.textContent = data.allergy_note;
                allergyEl.classList.remove('hidden');
            }
            const igEl = document.getElementById('instagram-link');
            if (data.instagram) {
                const handle = data.instagram.replace(/^@/, '');
                igEl.href = `https://instagram.com/${encodeURIComponent(handle)}`;
                igEl.textContent = '@' + handle;
                igEl.classList.remove('hidden');
            }
            const list = document.getElementById('branches-list');
            if (Array.isArray(data.branches)) {
                list.innerHTML = '';
                data.branches.forEach((b, i) => {
                    const row = document.createElement('div');
                    row.className = 'branch';
                    const tel = b.phone ? b.phone.replace(/[^\d+]/g, '') : '';
                    const telDisplay = b.phone ? b.phone.replace('+998', '+998 ').replace(/(\d{2})(\d{3})(\d{2})(\d{2})$/, '$1 $2 $3 $4') : '';
                    row.innerHTML = `
                        <span class="branch-pin"><svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 21s-7-6.2-7-11.5A7 7 0 0 1 19 9.5C19 14.8 12 21 12 21z"/><circle cx="12" cy="9.5" r="2.5"/></svg></span>
                        <span>
                            <div class="branch-name">${escapeHtml(b.name)}</div>
                            ${b.address ? `<div class="branch-address">${escapeHtml(b.address)}</div>` : ''}
                            ${tel ? `<a class="branch-phone" href="tel:${escapeHtml(tel)}">${escapeHtml(telDisplay)}</a>` : ''}
                        </span>`;
                    list.appendChild(rise(row, i));
                });
            }
        } catch (e) {
            console.error('Branches load error:', e);
        }
    }

    // ─── Старт ───
    function runSplash(ready) {
        const splash = document.getElementById('splash');
        let seen = false;
        try { seen = sessionStorage.getItem('mc_splash') === '1'; } catch (e) { /* приватный режим */ }
        const done = () => {
            document.body.classList.remove('is-loading');
            if (!splash) return;
            splash.classList.add('done');
            setTimeout(() => splash.remove(), 800);
            try { sessionStorage.setItem('mc_splash', '1'); } catch (e) { /* приватный режим */ }
        };
        if (seen || reduceMotion) { splash.remove(); document.body.classList.remove('is-loading'); return; }
        // Заставка держится, пока грузится меню, но не меньше секунды и не дольше трёх.
        const minDelay = new Promise(r => setTimeout(r, 1000));
        const maxDelay = new Promise(r => setTimeout(r, 3000));
        Promise.race([Promise.all([ready, minDelay]), maxDelay]).then(done);
    }

    buildHero();
    const ready = loadMenu();
    runSplash(ready);
    loadFact();
    loadBranches();
    onScroll();
})();
