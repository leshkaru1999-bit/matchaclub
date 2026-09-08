const tg = window.Telegram.WebApp;
tg.expand();

const API_BASE = ''; 

const app = {
    user: null,
    menuData: null,
    quizData: null,

    authHeaders() {
        return { 'X-Telegram-Init-Data': tg.initData || '' };
    },

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
                headers: { 'Content-Type': 'application/json', ...this.authHeaders() },
                body: JSON.stringify(user)
            });
            const data = await res.json();
            this.user = { ...user, stats: data.stats };
            this.rewardCost = data.reward_cost || 20;
            
            document.getElementById('points-val').textContent = data.stats.points;
            document.getElementById('user-points').classList.remove('hidden');
            
            if (!localStorage.getItem('rules_accepted')) {
                this.navigate('rules');
            } else {
                this.navigate('home');
            }
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

        const nav = document.getElementById('bottom-nav');
        const header = document.getElementById('header');
        if (page === 'rules') {
            if (nav) nav.style.display = 'none';
            if (header) header.style.display = 'none';
        } else {
            if (nav) nav.style.display = 'flex';
            if (header) header.style.display = 'flex';
        }

        const main = document.getElementById('main-content');
        const template = document.getElementById(`tpl-${page}`);
        
        if (template) {
            main.style.opacity = '0';
            setTimeout(async () => {
                main.innerHTML = '';
                main.appendChild(template.content.cloneNode(true));

                // Специфичная логика для страниц
                if (page === 'rules') {
                    const btn = document.getElementById('btn-accept-rules');
                    if (btn) {
                        btn.onclick = () => {
                            tg.HapticFeedback.impactOccurred('medium');
                            localStorage.setItem('rules_accepted', 'true');
                            this.navigate('home');
                        };
                    }
                }
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
            const res = await fetch(`${API_BASE}/api/fact`);
            const data = await res.json();
            // Convert HTML to plain text for Telegram popup
            let text = data.fact_html.replace(/<br\s*[\/]?>/gi, '\n');
            text = text.replace(/<[^>]*>?/gm, '');
            tg.showPopup({
                title: `💡 Факт дня`,
                message: text,
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
                        headers: { 'Content-Type': 'application/json', ...this.authHeaders() },
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

        let data = {};
        try {
            const resp = await fetch('/api/welcome');
            if (resp.ok) {
                data = await resp.json();
            }
        } catch (e) {
            console.error('Failed to load welcome book:', e);
        }

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
        const backBtn = document.getElementById('menu-back-btn');
        if (backBtn) backBtn.classList.add('hidden');

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
        const backBtn = document.getElementById('menu-back-btn');
        if (backBtn) backBtn.classList.remove('hidden');
        itemsGrid.innerHTML = '';

        category.items.forEach(item => {
            const div = document.createElement('div');
            div.className = 'menu-item-card premium-card';
            
            let html = '';
            if (item.photo_url) {
                html += `<div style="position: relative;">
                    <img src="${item.photo_url}" alt="${item.name}" class="menu-item-photo">
                    ${item.is_hit ? '<div class="hit-badge-photo">🔥 Хит</div>' : ''}
                </div>`;
            }
            
            let titleHit = (!item.photo_url && item.is_hit) ? '<span class="hit-badge-inline">🔥 Хит</span>' : '';
            html += `<div class="menu-item-info">
                <h3>${item.name} ${titleHit}</h3>`;
                
            if (item.description) {
                // В тексте описания иногда задублирован состав без иконки
                // (например "...\n\nСостав: Ингредиенты: ..."), а ниже он же
                // выводится отдельно с иконкой 🥗 из поля ingredients — обрезаем дубль.
                let desc = item.description;
                const dupIdx = desc.search(/\n*\s*Состав\s*:/i);
                if (dupIdx !== -1) desc = desc.slice(0, dupIdx).trim();
                if (desc) html += `<p class="menu-item-desc">${desc}</p>`;
            }

            if (item.ingredients) {
                html += `<p class="menu-item-ingredients" style="font-size: 13px; color: #555; margin-bottom: 5px;">🥗 <b>Состав:</b> ${item.ingredients}</p>`;
            }
            
            if (item.allergens) {
                html += `<p class="menu-item-allergens">⚠️ <b>Аллергены:</b> ${item.allergens}</p>`;
            }
            
            if (item.prep_time) {
                html += `<p class="menu-item-prep" style="font-size: 13px; color: #888; margin-bottom: 5px;">⏱ <b>Время готовки:</b> ${item.prep_time}</p>`;
            }
            
            if (item.audio) {
                html += `<div style="margin-top: 10px; margin-bottom: 10px;">
                    <p style="font-size: 12px; color: #666; margin-bottom: 5px; font-weight: 500;">🎙 Скрипт продаж:</p>
                    <audio controls style="width: 100%; height: 35px; border-radius: 8px;">
                        <source src="${API_BASE}/api/audio/${item.audio}" type="audio/mpeg">
                        <source src="${API_BASE}/api/audio/${item.audio}" type="audio/ogg">
                    </audio>
                </div>`;
            }
            
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
            const res = await fetch(`${API_BASE}/api/profile/${this.user.id}`, { headers: this.authHeaders() });
            const data = await res.json();
            const stats = data.stats || data;
            this.user.stats = stats;
            if (data.reward_cost) this.rewardCost = data.reward_cost;
            
            document.getElementById('points-val').textContent = stats.points;
            document.getElementById('prof-points').textContent = stats.points;
            document.getElementById('prof-quizzes').textContent = stats.quizzes_taken;
            document.getElementById('prof-rewards').textContent = stats.rewards_received || 0;
            
            let rank = "🍃 Стажёр";
            if (stats.points >= 100) rank = "👑 Мастер матчи";
            else if (stats.points >= 50) rank = "⭐ Эксперт";
            else if (stats.points >= 20) rank = "🌿 Знаток";
            document.getElementById('prof-rank').textContent = rank;

            const POINTS_FOR_DRINK = this.rewardCost || 20;
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
        const cost = this.rewardCost || 20;
        tg.showConfirm(`Потратить ${cost} баллов на 1 бесплатный напиток?`, async (confirmed) => {
            if (confirmed) {
                try {
                    const res = await fetch(`${API_BASE}/api/reward/request`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json', ...this.authHeaders() },
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
            answers: [],
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
            btn.onclick = () => this.handleAnswer(btn, idx, q.correct, q.explanation, q.id);
            optsContainer.appendChild(btn);
        });
    },

    handleAnswer(btn, selectedIdx, correctIdx, explanation, questionId) {
        const buttons = document.querySelectorAll('.option-btn');
        buttons.forEach(b => b.disabled = true);

        this.quizState.answers.push({ id: questionId, selected: selectedIdx });

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
                headers: { 'Content-Type': 'application/json', ...this.authHeaders() },
                body: JSON.stringify({
                    user_id: this.user.id,
                    answers: this.quizState.answers
                })
            });
            const data = await res.json();
            this.user.stats = data.new_stats;
            document.getElementById('points-val').textContent = data.new_stats.points;
            // Баллы и счёт начисляет сервер — обновляем экран результата актуальными цифрами
            if (typeof data.points_earned === 'number') {
                document.getElementById('quiz-res-points').textContent = data.points_earned;
            }
            if (typeof data.correct_answers === 'number') {
                document.getElementById('quiz-res-correct').textContent = data.correct_answers;
            }
            if (typeof data.wrong_answers === 'number') {
                document.getElementById('quiz-res-wrong').textContent = data.wrong_answers;
            }
        } catch (e) {}
    }
};

tg.ready();
app.init();
