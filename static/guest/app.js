(function () {
    const API_BASE = '..';
    const TYPE_LABELS = { kitchen: 'Кухня', bar: 'Бар' };

    function cleanCatName(name) {
        return (name || '').replace(/^[^\wа-яА-Я]+\s*/u, '').trim();
    }

    function escapeHtml(s) {
        const div = document.createElement('div');
        div.textContent = s || '';
        return div.innerHTML;
    }

    // В исходных данных иногда остаются ярлыки-заголовки вроде "Описание:\xa0"
    // или "Ингредиенты:" (а то и просто осиротевшее ":"), скопированные из
    // таблицы при заполнении меню. Для гостей это выглядит неряшливо — срезаем.
    function stripLabel(text, label) {
        if (!text) return text;
        const re = new RegExp(`^\\s*(?:(?:${label})\\s*:\\s*)?:?\\s*`, 'iu');
        return text.replace(re, '').trim();
    }

    function renderItemCard(item) {
        const card = document.createElement('div');
        card.className = 'item-card';

        let photoHtml = '';
        if (item.photo_url) {
            photoHtml = `<img src="${item.photo_url}" alt="${escapeHtml(item.name)}" loading="lazy">`;
        } else {
            photoHtml = `<span class="item-photo-placeholder">🍽️</span>`;
        }

        let html = `
            <div class="item-photo-wrap">
                ${photoHtml}
                ${item.is_hit ? '<div class="hit-badge">🔥 Хит</div>' : ''}
            </div>
            <div class="item-info">
                <div class="item-name-row">
                    <span class="item-name">${escapeHtml(item.name)}</span>
                    ${item.volume ? `<span class="item-volume">${escapeHtml(item.volume)}</span>` : ''}
                </div>
        `;

        if (item.description) {
            let desc = stripLabel(item.description, 'Описание');
            const dupIdx = desc.search(/\n*\s*Состав\s*:/i);
            if (dupIdx !== -1) desc = desc.slice(0, dupIdx).trim();
            if (desc) html += `<p class="item-desc">${escapeHtml(desc)}</p>`;
        }

        if (item.ingredients) {
            const ingr = stripLabel(item.ingredients, 'Ингредиенты|Состав');
            if (ingr) html += `<p class="item-ingredients"><b>Состав:</b> ${escapeHtml(ingr)}</p>`;
        }

        if (item.calories) {
            html += `
                <div class="kbzhu-row">
                    <span class="kbzhu-pill">${item.calories} ккал</span>
                    <span class="kbzhu-pill">Б ${item.protein ?? 0} г</span>
                    <span class="kbzhu-pill">Ж ${item.fat ?? 0} г</span>
                    <span class="kbzhu-pill">У ${item.carbs ?? 0} г</span>
                </div>
            `;
        }

        if (item.allergens) {
            html += `<span class="item-allergens">⚠️ Аллергены: ${escapeHtml(item.allergens)}</span>`;
        }

        html += `</div>`;
        card.innerHTML = html;
        return card;
    }

    function renderMenu(categories) {
        const root = document.getElementById('menu-root');
        const navInner = document.getElementById('cat-nav-inner');
        root.innerHTML = '';
        navInner.innerHTML = '';

        const order = ['kitchen', 'bar'];
        const grouped = order.map(t => ({ type: t, cats: categories.filter(c => c.type === t) }))
            .filter(g => g.cats.length > 0);

        grouped.forEach(group => {
            group.cats.forEach(cat => {
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

                const h2 = document.createElement('h2');
                h2.textContent = cat.name;
                section.appendChild(h2);

                const grid = document.createElement('div');
                grid.className = 'item-grid';
                cat.items.forEach(item => grid.appendChild(renderItemCard(item)));
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
        }, { rootMargin: '-120px 0px -70% 0px', threshold: 0 });

        sections.forEach(s => observer.observe(s));
        setActive(sections[0].id);
    }

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

    loadMenu();
    loadFact();
})();
