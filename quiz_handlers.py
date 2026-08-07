
async def handle_admin_quiz_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text == '/cancel':
        context.user_data['awaiting_quiz_add'] = False
        await update.message.reply_text("❌ Добавление отменена.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 В меню квиза", callback_data="adm_quiz_mgmt")]]))
        return True
        
    step = context.user_data.get('quiz_add_step')
    new_q = context.user_data.get('quiz_new_q', {})
    
    if step == 'QUESTION':
        new_q['question'] = text
        context.user_data['quiz_add_step'] = 'OPTIONS'
        await update.message.reply_text(
            "Отлично. Теперь отправь <b>4 варианта ответа</b>, каждый с новой строки.\nНапример:\nВариант 1\nВариант 2\nВариант 3\nВариант 4",
            parse_mode='HTML'
        )
    elif step == 'OPTIONS':
        options = [o.strip() for o in text.split('\n') if o.strip()]
        if len(options) != 4:
            await update.message.reply_text("❌ Нужно ровно 4 варианта. Попробуй еще раз.")
            return True
        new_q['options'] = options
        context.user_data['quiz_add_step'] = 'CORRECT'
        await update.message.reply_text("Какой из них правильный? Отправь <b>цифру от 1 до 4</b>.", parse_mode='HTML')
    elif step == 'CORRECT':
        if not text.isdigit() or not (1 <= int(text) <= 4):
            await update.message.reply_text("❌ Нужно отправить цифру от 1 до 4. Попробуй еще раз.")
            return True
        new_q['correct'] = int(text) - 1  # 0-indexed
        context.user_data['quiz_add_step'] = 'EXPLANATION'
        await update.message.reply_text("Супер! Теперь напиши объяснение (почему именно этот ответ правильный).", parse_mode='HTML')
    elif step == 'EXPLANATION':
        new_q['explanation'] = text
        quiz_data = load_quiz()
        max_id = max([q['id'] for q in quiz_data.get('questions', [])], default=0)
        new_q['id'] = max_id + 1
        quiz_data.setdefault('questions', []).append(new_q)
        save_quiz(quiz_data)
        
        context.user_data['awaiting_quiz_add'] = False
        await update.message.reply_text("✅ Вопрос успешно добавлен!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 В меню квиза", callback_data="adm_quiz_mgmt")]]))
    return True

async def handle_admin_quiz_cost_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text == '/cancel':
        context.user_data['awaiting_quiz_cost'] = False
        await update.message.reply_text("❌ Отменено.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 В меню квиза", callback_data="adm_quiz_mgmt")]]))
        return True
        
    if not text.isdigit():
        await update.message.reply_text("❌ Введи число (например: 20).")
        return True
        
    save_settings_val('points_for_drink', int(text))
    context.user_data['awaiting_quiz_cost'] = False
    await update.message.reply_text(f"✅ Цена награды успешно изменена на {text} баллов!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 В меню квиза", callback_data="adm_quiz_mgmt")]]))
    return True
