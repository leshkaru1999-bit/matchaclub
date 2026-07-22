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

    // ─── Велком-бук ───────────────────────────────────────────
    async loadWelcome() {
        const container = document.getElementById('welcome-sections');
        const msgEl = document.getElementById('welcome-company-msg');

        try {
            const res = await fetch(`${API_BASE}/api/welcome`);
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const data = await res.json();

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
        } catch (e) {
            console.error('Ошибка загрузки велком-бука:', e);
            if (container) {
                container.innerHTML = `<div class="premium-card" style="padding:20px;text-align:center;color:var(--danger)">
                    ⚠️ Не удалось загрузить данные.<br><small>${e.message}</small>
                </div>`;
            }
        }
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
            if (item.ingredients) html += `<p class="menu-item-ingredients" style="font-size: 0.85em; color: var(--tg-theme-hint-color, #888); margin-top: 4px;"><b>Состав:</b> ${item.ingredients}</p>`;
            
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

    async initQuizPage() {
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
        
        document.getElementById('quiz-intro').classList.add('hidden');
        document.getElementById('quiz-process').classList.remove('hidden');
        
        this.quizState = {
            questions: [...this.quizData.questions].sort(() => 0.5 - Math.random()).slice(0, 15),
            currentIdx: 0,
            correct: 0,
            wrong: 0
        };
        
        this.renderQuestion();
    },

    renderQuestion() {
        const q = this.quizState.questions[this.quizState.currentIdx];
        document.getElementById('quiz-progress').textContent = `${this.quizState.currentIdx + 1}/15`;
        document.getElementById('quiz-score').textContent = `Баллы: ${this.quizState.correct - (this.quizState.wrong * 2)}`;
        
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
