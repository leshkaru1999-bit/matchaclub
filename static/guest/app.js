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

    function photoInnerHtml(item, alt) {
        if (item.photo_url) {
            return `<img src="${item.photo_url}" alt="${escapeHtml(alt)}" loading="lazy">`;
        }
        return `<span class="item-photo-placeholder">🍽️</span>`;
    }

    function renderItemCard(item) {
        const card = document.createElement('div');
        card.className = 'item-card';

        card.innerHTML = `
            ${item.is_hit ? '<div class="hit-badge">🔥 Хит</div>' : ''}
            <div class="zoom-hint">＋</div>
            ${photoInnerHtml(item, item.name)}
            <div class="item-card-overlay">
                <div class="item-card-name">${escapeHtml(item.name)}</div>
                <div class="item-card-meta-row">
                    ${item.calories ? `<span class="item-card-kcal">${item.calories} ккал</span>` : '<span></span>'}
                    ${item.price ? `<span class="item-card-price">${formatPrice(item.price)}</span>` : ''}
                </div>
            </div>
        `;
        card.onclick = () => openDishModal(item);
        return card;
    }

    function renderMenu(categories) {
        const root = document.getElementById('menu-root');
        const navInner = document.getElementById('cat-nav-inner');
        root.innerHTML = '';
        navInner.innerHTML = '';

        // Некоторые позиции сняты с публичной витрины (hidden_from_guest), но
        // остаются в боте для сотрудников — гостям их показывать не нужно.
        const visible = (items) => items.filter(it => !it.hidden_from_guest);

        const order = ['kitchen', 'bar'];
        const grouped = order.map(t => ({ type: t, cats: categories.filter(c => c.type === t) }))
            .filter(g => g.cats.length > 0);

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
                section.className = 'menu-section';
                section.id = `cat-${cat.id}`;

                const head = document.createElement('div');
                head.className = 'menu-section-head';
                head.innerHTML = `<h2>${escapeHtml(cat.name)}</h2><span class="count">${items.length}</span>`;
                section.appendChild(head);

                const grid = document.createElement('div');
                grid.className = 'item-grid';
                items.forEach(item => grid.appendChild(renderItemCard(item)));
                section.appendChild(grid);

                root.appendChild(section);
            });
        });

        setupActiveChipTracking();
    }

    function setupActiveChipTracking() {
        const sections = Array.from(document.querySelectorAll('.menu-section'));
        const chips = Array.from(document.querySelectorAll('.cat-chip'));
        if (!sections.length) return;

        const setActive = (id) => {
            chips.forEach(c => c.classList.toggle('active', c.dataset.target === id));
            const activeChip = chips.find(c => c.dataset.target === id);
            if (activeChip) activeChip.scrollIntoView({ behavior: 'smooth', inline: 'center', block: 'nearest' });
        };

        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) setActive(entry.target.id);
            });
        }, { rootMargin: '-130px 0px -70% 0px', threshold: 0 });

        sections.forEach(s => observer.observe(s));
        setActive(sections[0].id);
    }

    function openDishModal(item) {
        const modal = document.getElementById('dish-modal');

        document.getElementById('dish-modal-photo').innerHTML = photoInnerHtml(item, item.name);
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
            kbzhuEl.innerHTML = `
                <span class="kbzhu-pill">${item.calories} ккал</span>
                <span class="kbzhu-pill">Б ${item.protein ?? 0} г</span>
                <span class="kbzhu-pill">Ж ${item.fat ?? 0} г</span>
                <span class="kbzhu-pill">У ${item.carbs ?? 0} г</span>
            `;
            kbzhuEl.style.display = '';
        } else {
            kbzhuEl.innerHTML = '';
            kbzhuEl.style.display = 'none';
        }

        const ingr = cleanIngredients(item.ingredients);
        const ingrEl = document.getElementById('dish-modal-ingredients');
        ingrEl.innerHTML = ingr ? `<b>Состав:</b> ${escapeHtml(ingr)}` : '';
        ingrEl.style.display = ingr ? '' : 'none';

        const allergensEl = document.getElementById('dish-modal-allergens');
        allergensEl.textContent = item.allergens ? `⚠️ Аллергены: ${item.allergens}` : '';

        modal.classList.add('open');
        document.body.style.overflow = 'hidden';
    }

    function closeDishModal() {
        document.getElementById('dish-modal').classList.remove('open');
        document.body.style.overflow = '';
    }

    document.getElementById('dish-modal-close').onclick = closeDishModal;
    document.querySelector('.dish-modal-backdrop').onclick = closeDishModal;
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') closeDishModal();
    });

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
