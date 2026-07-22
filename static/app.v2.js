const tg = window.Telegram.WebApp;
tg.expand();

const API_BASE = ''; 

const app = {
    user: null,
    menuData: null,
    quizData: null,
    
    init() {
        const initDataUnsafe = tg.initDataUnsafe;
        const user = initDataUnsafe.user || {
            id: 123456, 
            first_name: "Тест",
            username: "tester"
        };
        
        // Настройка темы
        document.documentElement.style.setProperty('--tg-theme-bg-color', tg.themeParams.bg_color || '#FFF9E9');
        document.documentElement.style.setProperty('--tg-theme-text-color', tg.themeParams.text_color || '#292D4C');
        document.documentElement.style.setProperty('--tg-theme-button-color', tg.themeParams.button_color || '#454C7F');
        document.documentElement.style.setProperty('--tg-theme-button-text-color', tg.themeParams.button_text_color || '#ffffff');

        this.applyThemeLogic(tg.colorScheme);
        tg.onEvent('themeChanged', () => this.applyThemeLogic(tg.colorScheme));

        this.initUser(user);
        this.setupNavigation();
    },

    applyThemeLogic(scheme) {
        const isDark = scheme === 'dark';
        document.querySelectorAll('.logo-light').forEach(el => el.classList.toggle('hidden', isDark));
        document.querySelectorAll('.logo-dark').forEach(el => el.classList.toggle('hidden', !isDark));
    },

    async initUser(user) {
        try {
            const res = await fetch(`${API_BASE}/api/init_user`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(user)
            });
            const data = await res.json();
            this.user = { ...user, stats: data.stats };
            
            document.getElementById('points-val').textContent = data.stats.points;
            document.getElementById('user-points').classList.remove('hidden');
            
            this.navigate('home');
        } catch (e) {
            console.error(e);
            document.getElementById('main-content').innerHTML = '<div class="loader"><p>Ошибка сети. Попробуйте позже.</p></div>';
        }
    },

    setupNavigation() {
        document.querySelectorAll('.nav-item').forEach(btn => {
            btn.addEventListener('click', () => {
                tg.HapticFeedback.impactOccurred('light');
                this.navigate(btn.dataset.target);
            });
        });
    },

    navigate(page) {
        document.querySelectorAll('.nav-item').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.target === page);
        });

        const main = document.getElementById('main-content');
        const template = document.getElementById(`tpl-${page}`);
        
        if (template) {
            main.style.opacity = '0';
            setTimeout(async () => {
                main.innerHTML = '';
                main.appendChild(template.content.cloneNode(true));

                // Специфичная логика для страниц
                if (page === 'home') this.applyThemeLogic(tg.colorScheme);
                if (page === 'menu') this.loadMenu();
                if (page === 'welcome') await this.loadWelcome();
                if (page === 'profile') this.loadProfile();
                if (page === 'quiz') this.initQuizPage();
                if (page === 'tour') await this.loadTour();

                // Плавное появление нового
                main.style.opacity = '1';
                main.style.transition = 'opacity 0.2s ease';
            }, 150);
        }

    },

    async showFact() {
        tg.HapticFeedback.impactOccurred('medium');
        try {
            const res = await fetch(`${API_BASE}/api/facts/random`);
            const fact = await res.json();
            tg.showPopup({
                title: `${fact.emoji} Факт дня`,
                message: fact.text,
                buttons: [{type: "ok"}]
            });
        } catch (e) {
            tg.showAlert('Не удалось загрузить факт.');
        }
    },

    showAttendanceMenu() {
        tg.HapticFeedback.impactOccurred('medium');
        tg.showPopup({
            title: 'Отметка на смене',
            message: 'Пожалуйста, выберите действие (приложение запросит вашу геолокацию):',
            buttons: [
                {type: 'default', text: '🟢 Приход', id: 'IN'},
                {type: 'destructive', text: '🔴 Уход', id: 'OUT'}
            ]
        }, (buttonId) => {
            if (buttonId) {
                this.logAttendance(buttonId);
            }
        });
    },

    logAttendance(action) {
        if (!navigator.geolocation) {
            tg.showAlert('Ваш браузер или устройство не поддерживает геолокацию.');
            return;
        }

        tg.HapticFeedback.impactOccurred('medium');
        // Показываем лоадер
        document.getElementById('main-content').style.opacity = '0.5';

        navigator.geolocation.getCurrentPosition(
            async (position) => {
                const lat = position.coords.latitude;
                const lon = position.coords.longitude;

                try {
                    const res = await fetch(`${API_BASE}/api/attendance`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            user_id: this.user.id,
                            first_name: this.user.first_name,
                            username: this.user.username,
                            action: action,
                            latitude: lat,
                            longitude: lon
                        })
                    });

                    if (res.ok) {
                        tg.HapticFeedback.notificationOccurred('success');
                        tg.showAlert('✅ Вы успешно отметились!');
                    } else {
                        throw new Error('Server error');
                    }
                } catch (e) {
                    console.error(e);
                    tg.HapticFeedback.notificationOccurred('error');
                    tg.showAlert('❌ Ошибка при отправке отметки.');
                } finally {
                    document.getElementById('main-content').style.opacity = '1';
                }
            },
            (error) => {
                tg.HapticFeedback.notificationOccurred('error');
                document.getElementById('main-content').style.opacity = '1';
                tg.showAlert('❌ Не удалось получить геолокацию. Убедитесь, что вы разрешили доступ к местоположению в настройках Telegram/устройства.');
            },
            { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 }
        );
    },

    // ─── Велком-бук ───────────────────────────────────────────
    async loadWelcome() {
        const container = document.getElementById('welcome-sections');
        const msgEl = document.getElementById('welcome-company-msg');

        const data = {
          "company_name": "Matcha Club & Mari Wellness",
          "welcome_message": "🍵 Добро пожаловать в Matcha Club & Mari Wellness!\n\nМы создаем современные пространства, где люди могут чувствовать комфорт, заботу и внутренний баланс.",
          "sections": [
            {
              "id": "about",
              "title": "📖 О компании",
              "content": "Matcha Club & Mari Wellness — это современная ресторанная группа, объединяющая проекты здорового образа жизни, гастрономии и атмосферы.\n\nМы создаем пространства, где люди приходят:\n• за вкусной и полезной едой\n• за эстетикой\n• за атмосферой\n• за отдыхом\n\n<b>Главный принцип компании:</b>\nМы создаем не просто рестораны.\nМы создаем состояние, в которое хочется возвращаться."
            },
            {
              "id": "mission",
              "title": "🎯 Миссия",
              "content": "Наша миссия — не только создавать красивые гастрономические проекты, но и популяризировать wellness-направление и культуру осознанного образа жизни.\n\nМы хотим показать, что вкусная еда может быть одновременно:\n• полезной\n• сбалансированной\n• эстетичной\n• современной\n\nМы верим, что питание влияет не только на физическое состояние человека, но и на его настроение, энергию и качество жизни.\n\nMatcha Club & Mari Wellness — это не просто кафе. Это пространства, куда приходят за состоянием, атмосферой и ощущением заботы."
            },
            {
              "id": "philosophy",
              "title": "💫 Философия",
              "content": "Мы верим, что сильный ресторан — это не только кухня и интерьер. Это прежде всего люди, которые создают атмосферу.\n\nФилософия строится на трех простых вещах:\n• <b>Забота</b>\n• <b>Внимание</b>\n• <b>Искренность</b>\n\nМы стараемся делать все так, чтобы гость чувствовал себя желанным. Не просто обслуженным — а именно желанным.\n\nМы уделяем внимание деталям:\n• как мы встречаем гостей\n• как мы подаем блюда\n• как мы разговариваем\n• как мы прощаемся\n\nИменно из деталей складывается впечатление."
            },
            {
              "id": "dna",
              "title": "🧬 ДНК компании",
              "content": "<b>5 принципов, которые отличают нас:</b>\n\n1️⃣ <b>Атмосфера важнее всего</b>\nГость приходит за ощущением — за спокойствием, эстетикой, уютом.\n\n2️⃣ <b>Сервис — это искренность</b>\nМы встречаем гостей как хороших знакомых — с уважением и теплом.\n\n3️⃣ <b>Детали создают впечатление</b>\nАккуратность, чистота, скорость, культура общения.\n\n4️⃣ <b>Команда — сердце компании</b>\nСотрудники уважают, помогают и работают на общий результат.\n\n5️⃣ <b>Мы создаем места, куда хочется возвращаться</b>\nЕсли гость уходит с ощущением заботы — мы сделали свою работу правильно."
            },
            {
              "id": "values",
              "title": "💎 Наши ценности",
              "content": "1. <b>Забота о человеке</b> — комфорт, внимание, эмоциональное спокойствие\n2. <b>Wellness как стиль жизни</b> — баланс, осознанное питание\n3. <b>Вкус и польза вместе</b> — вкусно, красиво, полезно\n4. <b>Искренний сервис</b> — уважение, внимание, искренность\n5. <b>Эстетика в деталях</b> — визуальная подача, атмосфера\n6. <b>Команда — сердце компании</b> — поддержка, рост вместе\n7. <b>Развитие и рост</b> — качество сервиса, продукт, культура\n8. <b>Ответственность</b> — каждый влияет на репутацию"
            },
            {
              "id": "goals",
              "title": "🏆 Наши цели",
              "content": "1. Популяризация wellness-культуры в Узбекистане\n2. Создание сильного гастрономического бренда\n3. Высокий уровень сервиса\n4. Формирование сообщества\n5. Развитие команды\n6. Развитие сети проектов\n7. Создание атмосферы комфорта\n8. Качество во всем"
            },
            {
              "id": "rules",
              "title": "📋 Правила компании",
              "content": "1. Мы не ищем виноватых — мы ищем решения\n2. Слово «увольнение» не является рабочим инструментом\n3. Уважение — основа нашей команды\n4. Мы не обсуждаем коллег за спиной\n5. Мы не обсуждаем гостей\n6. Гость всегда должен чувствовать заботу\n7. Чистота — ответственность каждого\n8. Мы не говорим «это не моя работа»\n9. Мы соблюдаем субординацию\n10. Мы не выносим внутренние процессы наружу\n11. Мы бережно относимся к имуществу\n12. Мы не терпим токсичность\n13. Мы развиваемся\n14. Мы гордимся своей работой\n15. Мы команда\n\n<b>Три ключевых правила:</b>\n⏰ Правило 24 часов — конфликты решаются в течение суток\n👑 Гость в приоритете — все процессы вокруг комфорта гостя\n✅ Ошибся — исправь — честность и ответственность"
            },
            {
              "id": "codex",
              "title": "⭐ Кодекс идеального сотрудника",
              "content": "1. <b>Уважение</b> — к гостям, коллегам, руководству\n2. <b>Ответственность</b> — за работу, результат, атмосферу\n3. <b>Забота о госте</b> — предугадать потребности\n4. <b>Профессионализм</b> — знание меню, стандартов\n5. <b>Командность</b> — помощь коллегам\n6. <b>Честность</b> — не скрывать ошибки\n7. <b>Инициатива</b> — предлагать идеи, искать решения\n8. <b>Аккуратность</b> — чистота, внешний вид, порядок\n9. <b>Спокойствие</b> — даже в часы пик\n10. <b>Гордость за работу</b> в Matcha Club & Mari Wellness"
            },
            {
              "id": "service",
              "title": "🤝 Хороший сервис",
              "content": "<b>10 фраз, которые мы НИКОГДА не говорим гостю:</b>\n❌ Я не знаю → ✅ Сейчас уточню для вас\n❌ Это не моя зона → ✅ Я помогу и приглашу коллегу\n❌ Подождите → ✅ Сейчас подойду к вам\n❌ Это не от меня зависит\n❌ У нас этого нет\n❌ Это долго\n❌ Вы неправильно заказали\n❌ Это невозможно\n❌ У нас так не принято\n❌ Я занят\n\n<b>Алгоритм L.A.S.T.:</b>\n🔵 L — Listen (выслушать)\n🔵 A — Apologize (извиниться)\n🔵 S — Solve (решить)\n🔵 T — Thank (поблагодарить)"
            },
            {
              "id": "menu_features",
              "title": "🍽️ Особенности меню",
              "content": "<b>Кухня Matcha Club:</b>\n• Легкость и баланс блюд\n• Современная визуальная подача\n• Свежие и качественные продукты\n\n<b>Бар Matcha Club:</b>\n• Широкий выбор напитков на основе матчи\n• Авторские напитки, лимонады, смузи\n• Каждый напиток создается с учетом вкуса и эстетики\n\n<b>Кухня Mari Wellness:</b>\n• Ориентирована на современное здоровое питание\n• Питательные и сбалансированные блюда\n• Натуральные продукты"
            },
            {
              "id": "career",
              "title": "📈 Путь сотрудника",
              "content": "Каждый сотрудник проходит этапы адаптации:\n\n1️⃣ <b>Испытательный срок</b>\nЛинейные позиции: до 3 рабочих смен\nРуководящие позиции: от 2 недель\n\n2️⃣ <b>Стажировка</b> (2-4 недели)\nИзучение адаптационной тетради\nПосещение всех тренингов\n\n3️⃣ <b>Аттестация</b>\nКухня — бренд-шеф\nБар — шеф-бармен\nСервис — управляющий"
            }
          ]
        };

        if (msgEl) msgEl.textContent = data.welcome_message || '';

        if (!container) return;
        container.innerHTML = '';

        const sections = data.sections || [];
        if (sections.length === 0) {
            container.innerHTML = '<p style="text-align:center;color:var(--light-text)">Разделы не найдены</p>';
            return;
        }

        sections.forEach(section => {
            const card = document.createElement('div');
            card.className = 'welcome-section-card premium-card';
            const emoji = section.title.match(/^\p{Emoji}/u)?.[0] || '📌';
            const titleText = section.title.replace(/^\p{Emoji}\s*/u, '');
            card.innerHTML = `
                <div class="welcome-section-icon">${emoji}</div>
                <div class="welcome-section-text">
                    <h3>${titleText}</h3>
                </div>
                <span class="welcome-arrow">›</span>
            `;
            card.onclick = () => {
                tg.HapticFeedback.impactOccurred('light');
                this.renderWelcomeSection(section);
            };
            container.appendChild(card);
        });
    },

    renderWelcomeSection(section) {
        const main = document.getElementById('main-content');
        const tpl = document.getElementById('tpl-welcome-section');
        main.style.opacity = '0';
        setTimeout(() => {
            main.innerHTML = '';
            main.appendChild(tpl.content.cloneNode(true));

            document.getElementById('section-title').textContent = section.title;
            // Рендерим HTML (в content есть <b> теги)
            document.getElementById('section-body').innerHTML = (section.content || '')
                .replace(/\n/g, '<br>');

            document.getElementById('welcome-back-btn').onclick = () => {
                this.navigate('welcome');
            };

            main.style.opacity = '1';
            main.style.transition = 'opacity 0.2s ease';
        }, 150);
    },

    async loadMenu() {
        if (!this.menuData) {
            const res = await fetch(`${API_BASE}/api/menu`);
            this.menuData = await res.json();
        }
        
        document.querySelectorAll('.tab-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                tg.HapticFeedback.selectionChanged();
                document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
                e.target.classList.add('active');
                this.renderMenuCategories(e.target.dataset.type);
            });
        });
        
        this.renderMenuCategories('kitchen');
    },

    renderMenuCategories(type) {
        if (!type) type = document.querySelector('.tab-btn.active').dataset.type;
        const catsContainer = document.getElementById('categories-container');
        const itemsContainer = document.getElementById('items-container');
        
        catsContainer.innerHTML = '';
        catsContainer.classList.remove('hidden');
        itemsContainer.classList.add('hidden');

        const categories = this.menuData.categories.filter(c => c.type === type);
        
        categories.forEach(cat => {
            const div = document.createElement('div');
            div.className = 'category-card';
            div.textContent = cat.name;
            div.onclick = () => {
                tg.HapticFeedback.impactOccurred('light');
                this.renderMenuItems(cat.id);
            };
            catsContainer.appendChild(div);
        });
    },

    renderMenuItems(catId) {
        const category = this.menuData.categories.find(c => c.id === catId);
        if (!category) return;

        const catsContainer = document.getElementById('categories-container');
        const itemsContainer = document.getElementById('items-container');
        const itemsGrid = document.getElementById('items-grid');
        
        catsContainer.classList.add('hidden');
        itemsContainer.classList.remove('hidden');
        itemsGrid.innerHTML = '';

        category.items.forEach(item => {
            const div = document.createElement('div');
            div.className = 'menu-item-card premium-card';
            
            let html = '';
            if (item.photo_url) {
                html += `<img src="${item.photo_url}" alt="${item.name}" class="menu-item-photo">`;
            }
            html += `<div class="menu-item-info"><h3>${item.name}</h3>`;
            if (item.description) html += `<p class="menu-item-desc">${item.description}</p>`;
            
            if (item.calories) {
                html += `<div class="kbzhu-container">
                    <span class="kbzhu-pill">${item.calories} ккал</span>
                    <span class="kbzhu-pill">Б ${item.protein}</span>
                    <span class="kbzhu-pill">Ж ${item.fat}</span>
                    <span class="kbzhu-pill">У ${item.carbs}</span>
                </div>`;
            }
            html += `</div>`;
            div.innerHTML = html;
            itemsGrid.appendChild(div);
        });
    },

    async loadTour() {
        try {
            const res = await fetch(`${API_BASE}/api/tour`);
            const data = await res.json();
            
            const container = document.getElementById('tour-videos');
            if (!container) return;
            
            container.innerHTML = '';
            
            if (data.videos && data.videos.length > 0) {
                data.videos.forEach(video => {
                    const card = document.createElement('div');
                    card.className = 'video-card animate-fade-in';
                    
                    let videoHtml = '';
                    if (video.type === 'youtube' && video.youtube_id) {
                        videoHtml = `
                            <div class="video-container">
                                <iframe src="https://www.youtube.com/embed/${video.youtube_id}?rel=0" title="${video.title}" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>
                            </div>
                        `;
                    } else if (video.type === 'mp4' && video.url) {
                        videoHtml = `
                            <div class="video-container">
                                <video controls preload="metadata" playsinline>
                                    <source src="${video.url}" type="video/mp4">
                                    Ваш браузер не поддерживает видео.
                                </video>
                            </div>
                        `;
                    }
                    
                    card.innerHTML = `
                        ${videoHtml}
                        <div class="video-info">
                            <h3>${video.title}</h3>
                            <p>${video.description}</p>
                        </div>
                    `;
                    container.appendChild(card);
                });
            } else {
                container.innerHTML = '<p style="text-align:center; color:var(--tg-theme-hint-color);">Видео пока не добавлены.</p>';
            }
        } catch (e) {
            console.error('Ошибка загрузки экскурсии:', e);
            const container = document.getElementById('tour-videos');
            if (container) {
                container.innerHTML = '<p style="text-align:center; color:red;">Ошибка загрузки видео</p>';
            }
        }
    },

    async loadProfile() {
        document.getElementById('prof-name').textContent = this.user.first_name;
        
        try {
            const res = await fetch(`${API_BASE}/api/profile/${this.user.id}`);
            const stats = await res.json();
            this.user.stats = stats;
            
            document.getElementById('points-val').textContent = stats.points;
            document.getElementById('prof-points').textContent = stats.points;
            document.getElementById('prof-quizzes').textContent = stats.quizzes_taken;
            document.getElementById('prof-rewards').textContent = stats.rewards_received || 0;
            
            let rank = "🍃 Стажёр";
            if (stats.points >= 100) rank = "👑 Мастер матчи";
            else if (stats.points >= 50) rank = "⭐ Эксперт";
            else if (stats.points >= 20) rank = "🌿 Знаток";
            document.getElementById('prof-rank').textContent = rank;

            const POINTS_FOR_DRINK = 20;
            const drinksAvailable = Math.floor(stats.points / POINTS_FOR_DRINK);
            const progress = stats.points % POINTS_FOR_DRINK;
            
            document.getElementById('prof-drinks').textContent = drinksAvailable;
            // Анимация прогресс-бара
            setTimeout(() => {
                document.getElementById('prof-progress').style.width = `${(progress / POINTS_FOR_DRINK) * 100}%`;
            }, 100);
            
            document.getElementById('prof-progress-text').textContent = `${progress} / ${POINTS_FOR_DRINK} баллов до следующего напитка`;
            
            const btnClaim = document.getElementById('btn-claim-reward');
            btnClaim.disabled = drinksAvailable === 0;
            btnClaim.onclick = () => this.requestReward();

            this.loadLeaderboard();
        } catch (e) {}
    },

    async requestReward() {
        tg.HapticFeedback.notificationOccurred('warning');
        tg.showConfirm('Потратить 20 баллов на 1 бесплатный напиток?', async (confirmed) => {
            if (confirmed) {
                try {
                    const res = await fetch(`${API_BASE}/api/reward/request`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ user_id: this.user.id })
                    });
                    if (res.ok) {
                        tg.HapticFeedback.notificationOccurred('success');
                        tg.showAlert('✨ Запрос отправлен! Покажите это сообщение администратору для получения напитка.');
                        this.loadProfile();
                    } else {
                        tg.showAlert('Ошибка при обмене.');
                    }
                } catch (e) {
                    tg.showAlert('Ошибка сети.');
                }
            }
        });
    },

    async loadLeaderboard() {
        try {
            const res = await fetch(`${API_BASE}/api/leaderboard`);
            const data = await res.json();
            const list = document.getElementById('leaderboard-list');
            list.innerHTML = '';
            
            data.leaders.forEach((l, i) => {
                let medal = `${i+1}.`;
                if(i===0) medal = '🥇'; if(i===1) medal = '🥈'; if(i===2) medal = '🥉';
                
                const name = l.first_name || l.username || 'Аноним';
                const div = document.createElement('div');
                div.className = 'leaderboard-list-item';
                div.innerHTML = `
                    <span class="leaderboard-name"><span style="margin-right:10px; opacity:0.8;">${medal}</span> ${name}</span>
                    <span class="leaderboard-score">${l.points}</span>
                `;
                list.appendChild(div);
            });
        } catch(e) {}
    },

    // ─── QUIZ (умный генератор без повторений) ───────────────
    QUIZ_STORAGE_KEY: 'matchaclub_seen_questions',
    QUIZ_SESSION_SIZE: 10,

    getSeenQuestions() {
        try {
            const stored = localStorage.getItem(this.QUIZ_STORAGE_KEY);
            return stored ? JSON.parse(stored) : [];
        } catch(e) { return []; }
    },

    saveSeenQuestions(seenIds) {
        try {
            localStorage.setItem(this.QUIZ_STORAGE_KEY, JSON.stringify(seenIds));
        } catch(e) {}
    },

    pickSessionQuestions(allQuestions) {
        let seenIds = this.getSeenQuestions();
        const allIds = allQuestions.map(q => q.id);

        // Фильтруем ещё не показанные вопросы
        let unseenQuestions = allQuestions.filter(q => !seenIds.includes(q.id));

        // Если непоказанных меньше чем нужно для сессии — сброс и берём все
        if (unseenQuestions.length < this.QUIZ_SESSION_SIZE) {
            // Добираем из уже показанных до нужного количества
            if (unseenQuestions.length === 0) {
                // Полный сброс
                seenIds = [];
                unseenQuestions = [...allQuestions];
                this.saveSeenQuestions([]);
            }
        }

        // Перемешиваем и берём нужное количество
        const shuffled = [...unseenQuestions].sort(() => Math.random() - 0.5);
        const session = shuffled.slice(0, this.QUIZ_SESSION_SIZE);

        // Запоминаем показанные
        const newSeenIds = [...new Set([...seenIds, ...session.map(q => q.id)])];
        this.saveSeenQuestions(newSeenIds);

        return { session, totalSeen: newSeenIds.length, totalAll: allQuestions.length };
    },

    updateBankUI(totalSeen, totalAll) {
        const pct = Math.round((totalSeen / totalAll) * 100);
        const remaining = totalAll - totalSeen;
        const fillEl = document.getElementById('bank-fill');
        const textEl = document.getElementById('bank-text');
        if (fillEl) {
            setTimeout(() => { fillEl.style.width = `${pct}%`; }, 100);
        }
        if (textEl) {
            if (remaining <= 0) {
                textEl.textContent = `🎉 Вы прошли весь банк (${totalAll} вопросов)! Банк сброшен.`;
            } else {
                textEl.textContent = `📚 Осталось вопросов: ${remaining} из ${totalAll}`;
            }
        }
    },

    async initQuizPage() {
        // Загружаем данные сразу чтобы показать прогресс банка
        if (!this.quizData) {
            try {
                const res = await fetch(`${API_BASE}/api/quiz`);
                this.quizData = await res.json();
            } catch (e) {}
        }
        if (this.quizData) {
            const seenIds = this.getSeenQuestions();
            const total = this.quizData.questions.length;
            const seen = seenIds.filter(id => this.quizData.questions.find(q => q.id === id)).length;
            this.updateBankUI(seen, total);
        }

        document.getElementById('btn-start-quiz').onclick = () => {
            tg.HapticFeedback.impactOccurred('medium');
            this.startQuiz();
        };
    },

    async startQuiz() {
        if (!this.quizData) {
            try {
                const res = await fetch(`${API_BASE}/api/quiz`);
                this.quizData = await res.json();
            } catch (e) {
                tg.showAlert('Не удалось загрузить квиз');
                return;
            }
        }

        const { session, totalSeen, totalAll } = this.pickSessionQuestions(this.quizData.questions);

        document.getElementById('quiz-intro').classList.add('hidden');
        document.getElementById('quiz-process').classList.remove('hidden');

        this.quizState = {
            questions: session,
            currentIdx: 0,
            correct: 0,
            wrong: 0,
            totalSeen,
            totalAll
        };

        this.renderQuestion();
    },

    renderQuestion() {
        const q = this.quizState.questions[this.quizState.currentIdx];
        const total = this.quizState.questions.length;
        document.getElementById('quiz-progress').textContent = `${this.quizState.currentIdx + 1}/${total}`;
        document.getElementById('quiz-score').textContent = `Баллы: ${Math.max(0, this.quizState.correct - (this.quizState.wrong * 2))}`;

        const qText = document.getElementById('quiz-question');
        qText.style.opacity = '0';
        qText.textContent = q.question;
        setTimeout(() => qText.style.opacity = '1', 50);

        const optsContainer = document.getElementById('quiz-options');
        optsContainer.innerHTML = '';

        q.options.forEach((opt, idx) => {
            const btn = document.createElement('button');
            btn.className = 'option-btn';
            btn.textContent = opt;
            btn.onclick = () => this.handleAnswer(btn, idx, q.correct, q.explanation);
            optsContainer.appendChild(btn);
        });
    },

    handleAnswer(btn, selectedIdx, correctIdx, explanation) {
        const buttons = document.querySelectorAll('.option-btn');
        buttons.forEach(b => b.disabled = true);

        if (selectedIdx === correctIdx) {
            tg.HapticFeedback.notificationOccurred('success');
            btn.classList.add('correct');
            this.quizState.correct++;
        } else {
            tg.HapticFeedback.notificationOccurred('error');
            btn.classList.add('wrong');
            buttons[correctIdx].classList.add('correct');
            this.quizState.wrong++;
        }

        tg.showPopup({
            title: selectedIdx === correctIdx ? '✅ Верно!' : '❌ Ошибка',
            message: explanation,
            buttons: [{type: 'ok', text: 'Дальше'}]
        }, () => {
            this.quizState.currentIdx++;
            if (this.quizState.currentIdx < this.quizState.questions.length) {
                this.renderQuestion();
            } else {
                this.finishQuiz();
            }
        });
    },

    async finishQuiz() {
        document.getElementById('quiz-process').classList.add('hidden');
        document.getElementById('quiz-result').classList.remove('hidden');

        const earned = Math.max(0, this.quizState.correct - (this.quizState.wrong * 2));

        document.getElementById('quiz-res-correct').textContent = this.quizState.correct;
        document.getElementById('quiz-res-wrong').textContent = this.quizState.wrong;
        document.getElementById('quiz-res-points').textContent = earned;

        // Показываем прогресс банка
        const remaining = this.quizState.totalAll - this.quizState.totalSeen;
        const bankTextEl = document.getElementById('result-bank-text');
        if (bankTextEl) {
            if (remaining <= 0) {
                bankTextEl.textContent = `🎉 Вы прошли весь банк! Следующий раунд начнётся заново.`;
            } else {
                bankTextEl.textContent = `📚 Осталось ещё ${remaining} новых вопросов`;
            }
        }

        // Кнопка «Ещё раунд»
        const playAgainBtn = document.getElementById('btn-play-again');
        if (playAgainBtn) {
            playAgainBtn.onclick = () => {
                tg.HapticFeedback.impactOccurred('medium');
                document.getElementById('quiz-result').classList.add('hidden');
                this.startQuiz();
            };
        }

        try {
            const res = await fetch(`${API_BASE}/api/quiz/submit`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    user_id: this.user.id,
                    correct_answers: this.quizState.correct,
                    wrong_answers: this.quizState.wrong,
                    points_earned: earned
                })
            });
            const data = await res.json();
            this.user.stats = data.new_stats;
            document.getElementById('points-val').textContent = data.new_stats.points;
        } catch (e) {}
    }
};

tg.ready();
app.init();
