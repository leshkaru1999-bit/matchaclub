
def load_quiz():
    from config import DATA_DIR
    import os, json
    path = os.path.join(DATA_DIR, 'quiz.json')
    if not os.path.exists(path):
        return {"questions": []}
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_quiz(data):
    from config import DATA_DIR
    import os, json
    path = os.path.join(DATA_DIR, 'quiz.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def save_settings_val(key, val):
    from config import DATA_DIR
    import os, json
    path = os.path.join(DATA_DIR, 'settings.json')
    data = {}
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    data[key] = val
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

async def admin_quiz_mgmt_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not is_admin(query.from_user):
        await query.answer("Нет доступа!")
        return
    await query.answer()
    
    quiz_data = load_quiz()
    q_count = len(quiz_data.get('questions', []))
    from config import get_settings
    cost = get_settings().get('points_for_drink', 100)
    
    text = (
        f"🎯 <b>Управление квизом и наградами</b>\n\n"
        f"Вопросов в базе: <b>{q_count}</b>\n"
        f"Стоимость награды: <b>{cost} баллов</b>\n\n"
        f"Выбери действие:"
    )
    buttons = [
        [InlineKeyboardButton("➕ Добавить вопрос", callback_data="adm_quiz_add")],
        [InlineKeyboardButton("📋 Список вопросов", callback_data="adm_quiz_list_0")],
        [InlineKeyboardButton("⚙️ Изменить цену награды", callback_data="adm_quiz_cost")],
        [InlineKeyboardButton("🔙 В меню", callback_data="adm_menu")]
    ]
    await query.message.edit_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(buttons))

async def admin_quiz_list_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not is_admin(query.from_user):
        await query.answer("Нет доступа!")
        return
    await query.answer()
    
    page = int(query.data.replace("adm_quiz_list_", ""))
    quiz_data = load_quiz()
    questions = quiz_data.get('questions', [])
    
    if not questions:
        await query.message.edit_text("📭 Вопросов нет.", reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Назад", callback_data="adm_quiz_mgmt")]
        ]))
        return
        
    per_page = 5
    start = page * per_page
    end = start + per_page
    page_items = questions[start:end]
    
    text = f"📋 <b>Список вопросов (Стр. {page+1})</b>\n\n"
    for q in page_items:
        text += f"<b>{q['id']}.</b> {q['question']}\n"
    
    buttons = []
    for q in page_items:
        buttons.append([InlineKeyboardButton(f"❌ Удал. {q['id']}", callback_data=f"adm_qdel_{q['id']}_{page}")])
        
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️", callback_data=f"adm_quiz_list_{page-1}"))
    if end < len(questions):
        nav.append(InlineKeyboardButton("➡️", callback_data=f"adm_quiz_list_{page+1}"))
    if nav:
        buttons.append(nav)
    
    buttons.append([InlineKeyboardButton("🔙 Назад", callback_data="adm_quiz_mgmt")])
    await query.message.edit_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(buttons))

async def admin_quiz_del_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not is_admin(query.from_user):
        await query.answer("Нет доступа!")
        return
    await query.answer()
    
    parts = query.data.split('_')
    q_id = int(parts[2])
    page = parts[3]
    
    quiz_data = load_quiz()
    quiz_data['questions'] = [q for q in quiz_data['questions'] if q['id'] != q_id]
    save_quiz(quiz_data)
    
    # Reload list
    query.data = f"adm_quiz_list_{page}"
    await admin_quiz_list_callback(update, context)

async def admin_quiz_add_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not is_admin(query.from_user):
        await query.answer("Нет доступа!")
        return
    await query.answer()
    
    context.user_data['awaiting_quiz_add'] = True
    context.user_data['quiz_add_step'] = 'QUESTION'
    context.user_data['quiz_new_q'] = {}
    
    await query.message.edit_text(
        "➕ <b>Добавление вопроса (Шаг 1/4)</b>\n\n"
        "Отправь текст вопроса.\n\n"
        "Для отмены отправь /cancel",
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Отмена", callback_data="adm_quiz_mgmt")]])
    )

async def admin_quiz_cost_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not is_admin(query.from_user):
        await query.answer("Нет доступа!")
        return
    await query.answer()
    
    context.user_data['awaiting_quiz_cost'] = True
    
    await query.message.edit_text(
        "⚙️ <b>Изменение цены награды</b>\n\n"
        "Введи новое количество баллов, необходимое для бесплатного напитка (например, 25).\n\n"
        "Для отмены отправь /cancel",
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Отмена", callback_data="adm_quiz_mgmt")]])
    )

# End of functions
