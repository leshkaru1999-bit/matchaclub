"""Обработчик админ-панели с управлением меню."""
import subprocess
import json
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters
import database as db
from config import ADMIN_ID, ADMIN_USERNAME, DATA_DIR


def is_admin(user) -> bool:
    """Super-admin (из .env) + админы добавленные через бот."""
    if ADMIN_ID and user.id == ADMIN_ID:
        return True
    if ADMIN_USERNAME and user.username and user.username.lower() == ADMIN_USERNAME:
        return True
    # Проверяем в БД
    if db.is_db_admin(user.id):
        return True
    return False


def is_superadmin(user) -> bool:
    """Только главный админ из .env может управлять другими админами."""
    if ADMIN_ID and user.id == ADMIN_ID:
        return True
    if ADMIN_USERNAME and user.username and user.username.lower() == ADMIN_USERNAME:
        return True
    return False


def load_menu():
    path = os.path.join(DATA_DIR, 'menu.json')
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"categories": []}


def save_menu(data):
    path = os.path.join(DATA_DIR, 'menu.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    # Сбрасываем кеш меню
    try:
        from handlers import menu as menu_handler
        menu_handler.reload_menu()
    except Exception:
        pass


def load_welcome():
    path = os.path.join(DATA_DIR, 'welcome.json')
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"sections": []}


def save_welcome(data):
    path = os.path.join(DATA_DIR, 'welcome.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


# ─── Роли ───────────────────────────────────────────────────────

ROLE_NAMES = {
    'full':    '👑 Полный доступ',
    'content': '📝 Контент',
}


def get_user_role(user) -> str:
    """Вернуть роль пользователя: 'superadmin', 'full', 'content' или None."""
    if is_superadmin(user):
        return 'superadmin'
    return db.get_admin_role(user.id)


def can_access(user, section: str) -> bool:
    """
    Проверка доступа к разделу.
    section: 'stats','users','rewards','broadcast','menu','welcome','tour','attendance','admins','gitpull'
    """
    role = get_user_role(user)
    if role == 'superadmin':
        return True
    if role == 'full':
        return section != 'admins'  # полный доступ везде кроме управления админами
    if role == 'content':
        return section in ('menu', 'welcome', 'tour')
    return False


# ─── Главное меню ───────────────────────────────────────────────

def get_admin_keyboard(user):
    role = get_user_role(user)
    buttons = []
    if role in ('superadmin', 'full'):
        buttons.append([
            InlineKeyboardButton("📊 Статистика", callback_data="adm_stats"),
            InlineKeyboardButton("👥 Пользователи", callback_data="adm_users"),
        ])
        buttons.append([
            InlineKeyboardButton("🎁 Награды", callback_data="adm_rewards"),
            InlineKeyboardButton("📤 Рассылка", callback_data="adm_bcast"),
        ])
    buttons.append([
        InlineKeyboardButton("🍽️ Управление меню", callback_data="adm_menu_mgmt"),
        InlineKeyboardButton("⏱ Смены", callback_data="adm_attendance"),
    ])
    buttons.append([
        InlineKeyboardButton("📖 Велком-бук", callback_data="adm_welcome_mgmt"),
        InlineKeyboardButton("🎬 Экскурсия", callback_data="adm_tour_mgmt"),
    ])
    buttons.append([
        InlineKeyboardButton("🎯 Квиз и Награды", callback_data="adm_quiz_mgmt"),
    ])
    if role == 'superadmin':
        buttons.append([
            InlineKeyboardButton("🔑 Администраторы", callback_data="adm_admins"),
        ])
        buttons.append([
            InlineKeyboardButton("🔄 Обновить с сервера", callback_data="adm_gitpull"),
        ])
    return InlineKeyboardMarkup(buttons)


async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user):
        await update.message.reply_text("❌ У тебя нет доступа к админ-панели.")
        return
    role = get_user_role(update.effective_user)
    role_label = {'superadmin': '👑 Суперадмин', 'full': '👑 Полный доступ', 'content': '📝 Контент'}.get(role, '')
    await update.message.reply_text(
        f"⚙️ <b>Админ-панель</b>  <i>({role_label})</i>\n\nВыбери действие 👇",
        parse_mode='HTML',
        reply_markup=get_admin_keyboard(update.effective_user)
    )


async def admin_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not is_admin(query.from_user):
        await query.answer("Нет доступа!")
        return
    await query.answer()
    role = get_user_role(query.from_user)
    role_label = {'superadmin': '👑 Суперадмин', 'full': '👑 Полный доступ', 'content': '📝 Контент'}.get(role, '')
    await query.message.edit_text(
        f"⚙️ <b>Админ-панель</b>  <i>({role_label})</i>\n\nВыбери действие 👇",
        parse_mode='HTML',
        reply_markup=get_admin_keyboard(query.from_user)
    )


async def admin_attendance_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not is_admin(query.from_user):
        await query.answer("Нет доступа!")
        return
    await query.answer()

    records = db.get_recent_attendance(20)
    if not records:
        text = "📭 <b>Отметки о сменах отсутствуют.</b>"
    else:
        text = "⏱ <b>Последние отметки (Приход / Уход)</b>\n\n"
        for r in records:
            action_icon = "🟢 Приход" if r.get('action_type') == 'IN' else "🔴 Уход"
            dt_str = r['checked_in_at'][:16] if r.get('checked_in_at') else "Неизвестно"
            name = r.get('first_name') or r.get('username') or f"ID {r['user_id']}"
            map_link = f"https://yandex.ru/maps/?pt={r['longitude']},{r['latitude']}&z=16&l=map"
            text += f"• <b>{dt_str}</b> | {name}\n  {action_icon} | <a href='{map_link}'>📍 Карта</a>\n\n"

    await query.message.edit_text(
        text,
        parse_mode='HTML',
        disable_web_page_preview=True,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Назад", callback_data="adm_menu")]
        ])
    )


# ─── Статистика ─────────────────────────────────────────────────

async def admin_stats_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not is_admin(query.from_user):
        await query.answer("Нет доступа!")
        return
    await query.answer()

    users_count = db.get_all_users_count()
    leaders = db.get_leaderboard(3)
    pending = db.get_pending_rewards()

    text = (
        f"📊 <b>Статистика бота</b>\n\n"
        f"👥 Пользователей: <b>{users_count}</b>\n"
        f"🎁 Ожидающих наград: <b>{len(pending)}</b>\n\n"
    )
    if leaders:
        text += "🏆 <b>Топ-3:</b>\n"
        medals = ["🥇", "🥈", "🥉"]
        for i, l in enumerate(leaders):
            name = l['first_name'] or l['username'] or '???'
            text += f"{medals[i]} {name} — {l['points']} б.\n"

    await query.message.edit_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Админ-панель", callback_data="adm_menu")],
    ]))


# ─── Пользователи ───────────────────────────────────────────────

async def admin_users_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not is_admin(query.from_user):
        await query.answer("Нет доступа!")
        return
    await query.answer()

    leaders = db.get_leaderboard(20)
    total = db.get_all_users_count()

    text = f"👥 <b>Пользователи</b> ({total} всего)\n\n"
    for i, user in enumerate(leaders, 1):
        name = user['first_name'] or '???'
        username = f"@{user['username']}" if user['username'] else ''
        text += f"{i}. {name} {username} — {user['points']}б, {user['quizzes_taken']} квизов\n"

    await query.message.edit_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Админ-панель", callback_data="adm_menu")],
    ]))


# ─── Награды ────────────────────────────────────────────────────

async def admin_rewards_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not is_admin(query.from_user):
        await query.answer("Нет доступа!")
        return
    await query.answer()

    pending = db.get_pending_rewards()

    if not pending:
        text = "🎁 <b>Ожидающие награды</b>\n\nНет активных запросов ✅"
        await query.message.edit_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Админ-панель", callback_data="adm_menu")],
        ]))
        return

    text = f"🎁 <b>Ожидающие награды ({len(pending)})</b>\n\n"
    buttons = []
    for r in pending:
        name = r['first_name'] or '???'
        username = f"@{r['username']}" if r['username'] else ''
        text += f"🎫 #{r['id']} — {name} {username}\n"
        buttons.append([
            InlineKeyboardButton(f"✅ #{r['id']} {name}", callback_data=f"adm_cr_{r['id']}"),
            InlineKeyboardButton(f"❌ #{r['id']}", callback_data=f"adm_rr_{r['id']}"),
        ])
    buttons.append([InlineKeyboardButton("🔙 Админ-панель", callback_data="adm_menu")])
    await query.message.edit_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(buttons))


async def admin_confirm_reward_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not is_admin(query.from_user):
        await query.answer("Нет доступа!")
        return
    await query.answer()
    reward_id = int(query.data.replace("adm_cr_", ""))
    db.confirm_reward(reward_id, query.from_user.id)
    await query.message.edit_text(
        f"✅ Награда #{reward_id} подтверждена!",
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🎁 Все награды", callback_data="adm_rewards")],
            [InlineKeyboardButton("🔙 Админ-панель", callback_data="adm_menu")],
        ])
    )


async def admin_reject_reward_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not is_admin(query.from_user):
        await query.answer("Нет доступа!")
        return
    await query.answer()
    reward_id = int(query.data.replace("adm_rr_", ""))
    db.reject_reward(reward_id, query.from_user.id)
    await query.message.edit_text(
        f"❌ Награда #{reward_id} отклонена. Баллы возвращены.",
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🎁 Все награды", callback_data="adm_rewards")],
            [InlineKeyboardButton("🔙 Админ-панель", callback_data="adm_menu")],
        ])
    )


# ─── Рассылка ───────────────────────────────────────────────────

async def admin_broadcast_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not is_admin(query.from_user):
        await query.answer("Нет доступа!")
        return
    await query.answer()
    context.user_data['awaiting_broadcast'] = True
    await query.message.edit_text(
        "📤 <b>Рассылка</b>\n\n"
        "Отправь мне текст сообщения для рассылки всем пользователям.\n\n"
        "Для отмены отправь /cancel",
        parse_mode='HTML'
    )


async def handle_broadcast_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user):
        return
    if not context.user_data.get('awaiting_broadcast'):
        # Проверяем другие режимы ожидания
        return
    context.user_data['awaiting_broadcast'] = False
    text = update.message.text
    if text == '/cancel':
        await update.message.reply_text("❌ Рассылка отменена.")
        return

    users = db.get_all_users()
    sent, failed = 0, 0
    status_msg = await update.message.reply_text(f"📤 Рассылка... 0/{len(users)}")
    for user_id in users:
        try:
            await context.bot.send_message(user_id, f"📢 <b>Matcha Club</b>\n\n{text}", parse_mode='HTML')
            sent += 1
        except Exception:
            failed += 1
        if (sent + failed) % 10 == 0:
            try:
                await status_msg.edit_text(f"📤 Рассылка... {sent + failed}/{len(users)}")
            except Exception:
                pass
    await status_msg.edit_text(
        f"✅ <b>Рассылка завершена!</b>\n\n📨 Отправлено: {sent}\n❌ Ошибок: {failed}",
        parse_mode='HTML'
    )


# ─── Управление меню ────────────────────────────────────────────

async def admin_menu_mgmt_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выбор типа меню для управления."""
    query = update.callback_query
    if not is_admin(query.from_user):
        await query.answer("Нет доступа!")
        return
    await query.answer()

    await query.message.edit_text(
        "🍽️ <b>Управление меню</b>\n\nВыбери раздел:",
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🍽️ Кухня", callback_data="adm_mcat_kitchen"),
                InlineKeyboardButton("🍹 Бар", callback_data="adm_mcat_bar"),
            ],
            [InlineKeyboardButton("🔙 Назад", callback_data="adm_menu")],
        ])
    )


async def admin_menu_cat_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Список категорий для выбранного типа."""
    query = update.callback_query
    if not is_admin(query.from_user):
        await query.answer("Нет доступа!")
        return
    await query.answer()

    menu_type = query.data.replace("adm_mcat_", "")
    data = load_menu()
    categories = [c for c in data['categories'] if c['type'] == menu_type]

    buttons = []
    for cat in categories:
        buttons.append([InlineKeyboardButton(cat['name'], callback_data=f"adm_mitem_{cat['id']}")])
    buttons.append([InlineKeyboardButton("🔙 Назад", callback_data="adm_menu_mgmt")])

    type_name = "Кухня" if menu_type == "kitchen" else "Бар"
    await query.message.edit_text(
        f"📂 <b>{type_name}</b>\n\nВыбери категорию:",
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(buttons)
    )


async def admin_menu_items_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Список блюд в категории с кнопками удаления."""
    query = update.callback_query
    if not is_admin(query.from_user):
        await query.answer("Нет доступа!")
        return
    await query.answer()

    cat_id = query.data.replace("adm_mitem_", "")
    data = load_menu()
    category = next((c for c in data['categories'] if c['id'] == cat_id), None)
    if not category:
        await query.message.edit_text("❌ Категория не найдена.")
        return

    # Сохраняем cat_id в context для возврата
    context.user_data['adm_cat_id'] = cat_id
    back_type = "adm_mcat_" + category['type']

    buttons = []
    for i, item in enumerate(category['items']):
        name = item['name']
        short = name[:28] + "…" if len(name) > 28 else name
        buttons.append([
            InlineKeyboardButton(f"🗑 {short}", callback_data=f"adm_del_{cat_id}_{i}"),
            InlineKeyboardButton("✏️", callback_data=f"adm_edit_{cat_id}_{i}"),
        ])

    buttons.append([InlineKeyboardButton("➕ Добавить блюдо", callback_data=f"adm_add_{cat_id}")])
    buttons.append([InlineKeyboardButton("🔙 Назад", callback_data=back_type)])

    text = f"📋 <b>{category['name']}</b>\n\n"
    text += f"Позиций: <b>{len(category['items'])}</b>\n\n"
    text += "🗑 — удалить   ✏️ — редактировать"

    await query.message.edit_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(buttons))


async def admin_delete_item_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Запрос подтверждения удаления."""
    query = update.callback_query
    if not is_admin(query.from_user):
        await query.answer("Нет доступа!")
        return
    await query.answer()

    parts = query.data.replace("adm_del_", "").rsplit("_", 1)
    cat_id = parts[0]
    item_idx = int(parts[1])

    data = load_menu()
    category = next((c for c in data['categories'] if c['id'] == cat_id), None)
    if not category or item_idx >= len(category['items']):
        await query.message.edit_text("❌ Блюдо не найдено.")
        return

    item_name = category['items'][item_idx]['name']

    await query.message.edit_text(
        f"⚠️ <b>Удалить блюдо?</b>\n\n«{item_name}»\n\nЭто действие нельзя отменить!",
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Да, удалить", callback_data=f"adm_delok_{cat_id}_{item_idx}"),
                InlineKeyboardButton("❌ Отмена", callback_data=f"adm_mitem_{cat_id}"),
            ],
        ])
    )


async def admin_delete_item_ok_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Подтверждённое удаление блюда."""
    query = update.callback_query
    if not is_admin(query.from_user):
        await query.answer("Нет доступа!")
        return
    await query.answer()

    parts = query.data.replace("adm_delok_", "").rsplit("_", 1)
    cat_id = parts[0]
    item_idx = int(parts[1])

    data = load_menu()
    category = next((c for c in data['categories'] if c['id'] == cat_id), None)
    if not category or item_idx >= len(category['items']):
        await query.message.edit_text("❌ Блюдо не найдено.")
        return

    removed_name = category['items'].pop(item_idx)['name']
    save_menu(data)

    await query.message.edit_text(
        f"✅ Блюдо <b>«{removed_name}»</b> удалено из меню.",
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 К категории", callback_data=f"adm_mitem_{cat_id}")],
            [InlineKeyboardButton("🏠 Админ-панель", callback_data="adm_menu")],
        ])
    )


async def admin_edit_item_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Редактирование блюда — выбор поля."""
    query = update.callback_query
    if not is_admin(query.from_user):
        await query.answer("Нет доступа!")
        return
    await query.answer()

    context.user_data.pop('awaiting_edit', None)

    parts = query.data.replace("adm_edit_", "").rsplit("_", 1)
    cat_id = parts[0]
    item_idx = int(parts[1])

    data = load_menu()
    category = next((c for c in data['categories'] if c['id'] == cat_id), None)
    if not category or item_idx >= len(category['items']):
        await query.message.edit_text("❌ Блюдо не найдено.")
        return

    item = category['items'][item_idx]

    text = (
        f"✏️ <b>Редактирование блюда</b>\n\n"
        f"<b>Название:</b> {item.get('name', '—')}\n"
        f"<b>Описание:</b> {item.get('description', '—')}\n"
        f"<b>Состав:</b> {item.get('ingredients', '—')}\n"
        f"<b>Объём:</b> {item.get('volume', '—')}\n"
        f"<b>КБЖУ:</b> {item.get('calories', 0)}/{item.get('protein', 0)}/{item.get('fat', 0)}/{item.get('carbs', 0)}\n"
        f"<b>Аллергены:</b> {item.get('allergens', '—')}\n"
        f"<b>Время готовки:</b> {item.get('prep_time', '—')}\n"
        f"<b>Хит продаж:</b> {'Да 🔥' if item.get('is_hit') else 'Нет'}\n\n"
        f"Выбери, что хочешь изменить:"
    )

    buttons = [
        [
            InlineKeyboardButton("✏️ Название", callback_data=f"adm_edf_name_{cat_id}_{item_idx}"),
            InlineKeyboardButton("📝 Описание", callback_data=f"adm_edf_desc_{cat_id}_{item_idx}")
        ],
        [
            InlineKeyboardButton("🥗 Состав", callback_data=f"adm_edf_ingr_{cat_id}_{item_idx}"),
            InlineKeyboardButton("📸 Фото", callback_data=f"adm_edf_photo_{cat_id}_{item_idx}")
        ],
        [
            InlineKeyboardButton("📊 КБЖУ", callback_data=f"adm_edf_macros_{cat_id}_{item_idx}"),
            InlineKeyboardButton("🥤 Объём", callback_data=f"adm_edf_volume_{cat_id}_{item_idx}")
        ],
        [
            InlineKeyboardButton("⚠️ Аллергены", callback_data=f"adm_edf_aller_{cat_id}_{item_idx}"),
            InlineKeyboardButton(f"🔥 Хит: {'Да' if item.get('is_hit') else 'Нет'}", callback_data=f"adm_edf_hit_{cat_id}_{item_idx}")
        ],
        [
            InlineKeyboardButton("⏱ Время готовки", callback_data=f"adm_edf_prep_{cat_id}_{item_idx}")
        ],
        [InlineKeyboardButton("🔙 Назад", callback_data=f"adm_mitem_{cat_id}")]
    ]
    await query.message.edit_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(buttons))


async def admin_edit_field_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not is_admin(query.from_user):
        await query.answer("Нет доступа!")
        return
    await query.answer()

    parts = query.data.replace("adm_edf_", "").split("_", 1)
    field = parts[0]
    rest = parts[1]
    
    cat_id, item_idx_str = rest.rsplit("_", 1)
    item_idx = int(item_idx_str)

    context.user_data['edit_field'] = field

    context.user_data['awaiting_edit'] = True
    context.user_data['edit_cat_id'] = cat_id
    context.user_data['edit_item_idx'] = item_idx
    context.user_data['edit_field'] = field

    if field == 'hit':
        context.user_data['awaiting_edit'] = False
        data = load_menu()
        category = next((c for c in data['categories'] if c['id'] == cat_id), None)
        if category and item_idx < len(category['items']):
            item = category['items'][item_idx]
            item['is_hit'] = not item.get('is_hit', False)
            save_menu(data)
            
            # Рендерим обновленную карточку сразу
            text = (
                f"✏️ <b>Редактирование блюда</b>\n\n"
                f"<b>Название:</b> {item.get('name', '—')}\n"
                f"<b>Описание:</b> {item.get('description', '—')}\n"
                f"<b>Состав:</b> {item.get('ingredients', '—')}\n"
                f"<b>Объём:</b> {item.get('volume', '—')}\n"
                f"<b>КБЖУ:</b> {item.get('calories', 0)}/{item.get('protein', 0)}/{item.get('fat', 0)}/{item.get('carbs', 0)}\n"
                f"<b>Аллергены:</b> {item.get('allergens', '—')}\n"
                f"<b>Время готовки:</b> {item.get('prep_time', '—')}\n"
                f"<b>Хит продаж:</b> {'Да 🔥' if item.get('is_hit') else 'Нет'}\n\n"
                f"Выбери, что хочешь изменить:"
            )
            buttons = [
                [
                    InlineKeyboardButton("✏️ Название", callback_data=f"adm_edf_name_{cat_id}_{item_idx}"),
                    InlineKeyboardButton("📝 Описание", callback_data=f"adm_edf_desc_{cat_id}_{item_idx}")
                ],
                [
                    InlineKeyboardButton("🥗 Состав", callback_data=f"adm_edf_ingr_{cat_id}_{item_idx}"),
                    InlineKeyboardButton("📸 Фото", callback_data=f"adm_edf_photo_{cat_id}_{item_idx}")
                ],
                [
                    InlineKeyboardButton("📊 КБЖУ", callback_data=f"adm_edf_macros_{cat_id}_{item_idx}"),
                    InlineKeyboardButton("🥤 Объём", callback_data=f"adm_edf_volume_{cat_id}_{item_idx}")
                ],
                [
                    InlineKeyboardButton("⚠️ Аллергены", callback_data=f"adm_edf_aller_{cat_id}_{item_idx}"),
                    InlineKeyboardButton(f"🔥 Хит: {'Да' if item.get('is_hit') else 'Нет'}", callback_data=f"adm_edf_hit_{cat_id}_{item_idx}")
                ],
                [
                    InlineKeyboardButton("⏱ Время готовки", callback_data=f"adm_edf_prep_{cat_id}_{item_idx}")
                ],
                [InlineKeyboardButton("🔙 Назад", callback_data=f"adm_mitem_{cat_id}")]
            ]
            await query.message.edit_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(buttons))
        return

    if field == 'name':
        prompt = "Отправь новое <b>Название</b> блюда (только текст).\nИли /cancel для отмены."
    elif field == 'desc':
        prompt = "Отправь новое <b>Описание</b> блюда (только текст).\nИли /cancel для отмены."
    elif field == 'ingr':
        prompt = "Отправь новый <b>Состав</b> блюда (только текст).\nИли /cancel для отмены."
    elif field == 'photo':
        prompt = "Отправь новую <b>Фотографию</b> блюда (изображением).\nИли /cancel для отмены."
    elif field == 'macros':
        prompt = "Отправь новые <b>КБЖУ</b> (через пробел или запятую: Калории Белки Жиры Углеводы).\nНапример: <code>250 15 10 30</code>\nИли /cancel для отмены."
    elif field == 'volume':
        prompt = "Отправь новый <b>Объём</b> порции (например: <code>250 мл</code>, <code>30 мл</code>, <code>500 г</code>).\nИли /cancel для отмены."
    elif field == 'aller':
        prompt = "Отправь список <b>Аллергенов</b> (например: <code>мед, орехи, молоко</code>).\nДля удаления отправь <code>-</code>.\nИли /cancel для отмены."
    elif field == 'prep':
        prompt = "Отправь <b>Время готовки</b> (например: <code>10-18 минут</code>).\nДля удаления отправь <code>-</code>.\nИли /cancel для отмены."

    await query.message.edit_text(prompt, parse_mode='HTML', reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Отмена", callback_data=f"adm_edit_{cat_id}_{item_idx}")]
    ]))

async def admin_add_item_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Добавление нового блюда — запрашиваем название."""
    query = update.callback_query
    if not is_admin(query.from_user):
        await query.answer("Нет доступа!")
        return
    await query.answer()

    cat_id = query.data.replace("adm_add_", "")
    data = load_menu()
    category = next((c for c in data['categories'] if c['id'] == cat_id), None)
    if not category:
        await query.message.edit_text("❌ Категория не найдена.")
        return

    context.user_data['awaiting_add'] = {
        'cat_id': cat_id,
        'step': 'NAME',
        'name': '',
        'description': '',
        'ingredients': '',
        'volume': '',
        'allergens': '',
        'prep_time': '',
        'is_hit': False
    }

    await query.message.edit_text(
        f"➕ <b>Добавить блюдо</b>\n\n"
        f"Категория: <b>{category['name']}</b>\n\n"
        f"Отправь название нового блюда.\n"
        f"Или /cancel для отмены.",
        parse_mode='HTML'
    )



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


async def handle_admin_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка текстовых ответов из режимов ожидания."""
    if not is_admin(update.effective_user):
        return

    text = update.message.text.strip() if update.message.text else ""
    photo = update.message.photo[-1] if update.message.photo else None

    # ── Добавление администратора ──
    if context.user_data.get('awaiting_quiz_add'):
        handled = await handle_admin_quiz_text(update, context)
        if handled: return
        
    if context.user_data.get('awaiting_quiz_cost'):
        handled = await handle_admin_quiz_cost_text(update, context)
        if handled: return

    if context.user_data.get('awaiting_add_admin'):
        handled = await handle_add_admin_text(update, context)
        if handled:
            return

    # ── Экскурсия ──
    if context.user_data.get('awaiting_tour'):
        handled = await handle_admin_tour_text(update, context)
        if handled:
            return

    # ── Велком-бук ──
    if context.user_data.get('awaiting_welcome'):
        handled = await handle_admin_welcome_text(update, context)
        if handled:
            return

    # ── Рассылка ──
    if context.user_data.get('awaiting_broadcast'):
        context.user_data['awaiting_broadcast'] = False
        if text == '/cancel':
            await update.message.reply_text("❌ Рассылка отменена.")
            return
        users = db.get_all_users()
        sent, failed = 0, 0
        status_msg = await update.message.reply_text(f"📤 Рассылка... 0/{len(users)}")
        for user_id in users:
            try:
                await context.bot.send_message(user_id, f"📢 <b>Matcha Club</b>\n\n{text}", parse_mode='HTML')
                sent += 1
            except Exception:
                failed += 1
            if (sent + failed) % 10 == 0:
                try:
                    await status_msg.edit_text(f"📤 Рассылка... {sent + failed}/{len(users)}")
                except Exception:
                    pass
        await status_msg.edit_text(
            f"✅ <b>Рассылка завершена!</b>\n\n📨 Отправлено: {sent}\n❌ Ошибок: {failed}",
            parse_mode='HTML'
        )
        return

    # ── Редактирование блюда ──
    if context.user_data.get('awaiting_edit'):
        context.user_data['awaiting_edit'] = False
        cat_id = context.user_data.pop('edit_cat_id', None)
        item_idx = context.user_data.pop('edit_item_idx', None)
        field = context.user_data.pop('edit_field', None)
        
        if text == '/cancel':
            await update.message.reply_text("❌ Редактирование отменено.")
            return

        if cat_id is None or item_idx is None or field is None:
            await update.message.reply_text("❌ Ошибка: контекст редактирования утерян.")
            return
            
        data = load_menu()
        category = next((c for c in data['categories'] if c['id'] == cat_id), None)
        if not category or item_idx >= len(category['items']):
            await update.message.reply_text("❌ Блюдо не найдено.")
            return
            
        item = category['items'][item_idx]
        
        if field == 'name':
            if not text:
                await update.message.reply_text("❌ Нужно отправить текст.")
                return
            item['name'] = text
        elif field == 'desc':
            if not text:
                await update.message.reply_text("❌ Нужно отправить текст.")
                return
            item['description'] = text
        elif field == 'ingr':
            if not text:
                await update.message.reply_text("❌ Нужно отправить текст.")
                return
            item['ingredients'] = text
        elif field == 'photo':
            if not photo:
                await update.message.reply_text("❌ Нужно отправить фото.")
                return
            import uuid
            from config import PHOTOS_DIR
            os.makedirs(PHOTOS_DIR, exist_ok=True)
            filename = f"item_{uuid.uuid4().hex[:8]}.jpg"
            photo_path = os.path.join(PHOTOS_DIR, filename)
            new_file = await photo.get_file()
            await new_file.download_to_drive(custom_path=photo_path)
            item['photo'] = filename
        elif field == 'macros':
            import re
            nums = re.findall(r'\d+', text) if text else []
            if len(nums) >= 4:
                item['calories'] = int(nums[0])
                item['protein'] = int(nums[1])
                item['fat'] = int(nums[2])
                item['carbs'] = int(nums[3])
            else:
                await update.message.reply_text("❌ Нужно отправить 4 числа.")
                return
        elif field == 'volume':
            if not text:
                await update.message.reply_text("❌ Нужно отправить текст (например: 250 мл).")
                return
            item['volume'] = text
        elif field == 'aller':
            if not text:
                await update.message.reply_text("❌ Нужно отправить текст.")
                return
            item['allergens'] = "" if text == "-" else text
        elif field == 'prep':
            if not text:
                await update.message.reply_text("❌ Нужно отправить текст.")
                return
            item['prep_time'] = "" if text == "-" else text
                
        save_menu(data)
        await update.message.reply_text(
            f"✅ Поле обновлено!",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Вернуться к блюду", callback_data=f"adm_edit_{cat_id}_{item_idx}")],
                [InlineKeyboardButton("🔙 К категории", callback_data=f"adm_mitem_{cat_id}")],
            ])
        )
        return

    # ── Добавление блюда (пошагово) ──
    add_state = context.user_data.get('awaiting_add')
    if add_state:
        if text == '/cancel':
            context.user_data.pop('awaiting_add', None)
            await update.message.reply_text("❌ Добавление отменено.")
            return

        cat_id = add_state.get('cat_id')
        step = add_state.get('step')

        if step == 'NAME':
            if not text:
                await update.message.reply_text("❌ Пожалуйста, отправьте название блюда текстом.")
                return
            add_state['name'] = text
            add_state['step'] = 'DESC'
            await update.message.reply_text(
                "✅ Название сохранено.\n\n"
                "Теперь отправь <b>Описание</b> блюда.\n"
                "<i>(Или отправь \"-\", чтобы пропустить)</i>",
                parse_mode='HTML'
            )
            return

        elif step == 'DESC':
            if not text:
                await update.message.reply_text("❌ Отправьте текст или \"-\".")
                return
            add_state['description'] = "" if text == "-" else text
            add_state['step'] = 'INGR'
            await update.message.reply_text(
                "✅ Описание сохранено.\n\n"
                "Теперь отправь <b>Состав</b> блюда.\n"
                "<i>(Или отправь \"-\", чтобы пропустить)</i>",
                parse_mode='HTML'
            )
            return

        elif step == 'INGR':
            if not text:
                await update.message.reply_text("❌ Отправьте текст или \"-\".")
                return
            
            ingr = "" if text == "-" else text
            add_state['ingredients'] = ingr
            
            # If they provided ingredients, automatically append to description like we did before
            if ingr:
                desc = add_state.get('description', '')
                add_state['description'] = f"{desc}\n\nСостав: {ingr}".strip()
                
            add_state['step'] = 'PHOTO'
            await update.message.reply_text(
                "✅ Состав сохранен.\n\n"
                "Наконец, отправь <b>Фотографию</b> блюда.\n"
                "<i>(Или отправь \"-\", чтобы добавить без фото)</i>",
                parse_mode='HTML'
            )
            return

        elif step == 'PHOTO':
            photo_filename = ""
            if photo:
                import uuid
                from config import PHOTOS_DIR
                os.makedirs(PHOTOS_DIR, exist_ok=True)
                ext = "jpg"
                filename = f"item_{uuid.uuid4().hex[:8]}.{ext}"
                photo_path = os.path.join(PHOTOS_DIR, filename)
                
                new_file = await photo.get_file()
                await new_file.download_to_drive(custom_path=photo_path)
                photo_filename = filename
            elif text != "-":
                await update.message.reply_text("❌ Отправьте фотографию или \"-\".")
                return

            add_state['photo'] = photo_filename
            add_state['step'] = 'MACROS'
            await update.message.reply_text(
                "✅ Фотография обработана.\n\n"
                "Наконец, введите <b>КБЖУ</b> (через пробел или запятую: Калории Белки Жиры Углеводы).\n"
                "Например: <code>250 15 10 30</code>\n"
                "<i>(Или отправь \"-\", чтобы пропустить и оставить по нулям)</i>",
                parse_mode='HTML'
            )
            return

        elif step == 'MACROS':
            calories, protein, fat, carbs = 0, 0, 0, 0
            if text and text != "-":
                import re
                nums = re.findall(r'\d+', text)
                if len(nums) >= 4:
                    calories = int(nums[0])
                    protein = int(nums[1])
                    fat = int(nums[2])
                    carbs = int(nums[3])
                else:
                    await update.message.reply_text("❌ Пожалуйста, введите 4 числа (К Б Ж У) или отправьте \"-\".")
                    return

            add_state['calories'] = calories
            add_state['protein'] = protein
            add_state['fat'] = fat
            add_state['carbs'] = carbs
            add_state['step'] = 'VOLUME'
            await update.message.reply_text(
                "✅ КБЖУ сохранено.\n\n"
                "Отправь <b>Объём</b> порции (например: <code>250 мл</code>, <code>30 мл</code>, <code>500 г</code>).\n"
                "<i>(Или отправь \"-\", чтобы пропустить)</i>",
                parse_mode='HTML'
            )
            return

        elif step == 'VOLUME':
            volume = "" if (not text or text == "-") else text
            add_state['volume'] = volume

            context.user_data.pop('awaiting_add', None)
            
            data = load_menu()
            category = next((c for c in data['categories'] if c['id'] == cat_id), None)
            if not category:
                await update.message.reply_text("❌ Категория не найдена.")
                return

            new_item = {
                "name": add_state['name'],
                "description": add_state['description'],
                "ingredients": add_state['ingredients'],
                "photo": add_state.get('photo', ""),
                "calories": add_state.get('calories', 0),
                "protein": add_state.get('protein', 0),
                "fat": add_state.get('fat', 0),
                "carbs": add_state.get('carbs', 0)
            }
            if add_state.get('volume'):
                new_item['volume'] = add_state['volume']
            category['items'].append(new_item)
            save_menu(data)
            
            photo_msg = "с фотографией" if add_state.get('photo') else "без фотографии"
            volume_msg = f", объём: {add_state['volume']}" if add_state.get('volume') else ""
            await update.message.reply_text(
                f"✅ Блюдо <b>«{add_state['name']}»</b> успешно добавлено ({photo_msg}{volume_msg}) в категорию <b>«{category['name']}»</b>.",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 К категории", callback_data=f"adm_mitem_{cat_id}")],
                ])
            )
            return


async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop('awaiting_broadcast', None)
    context.user_data.pop('awaiting_edit', None)
    context.user_data.pop('awaiting_add', None)
    context.user_data.pop('awaiting_welcome', None)
    context.user_data.pop('awaiting_add_admin', None)
    context.user_data.pop('awaiting_tour', None)
    await update.message.reply_text("❌ Действие отменено.")


# ─── Обновление с сервера (git pull) ──────────────────────────────

async def admin_gitpull_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Делает git pull и перезагружает кеш меню."""
    query = update.callback_query
    if not is_admin(query.from_user):
        await query.answer("Нет доступа!")
        return
    await query.answer()

    await query.message.edit_text(
        "🔄 <b>Обновление с сервера...</b>\n\nВыполняю <code>git pull</code>, подожди...",
        parse_mode='HTML'
    )

    try:
        import os
        repo_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        result = subprocess.run(
            ['git', 'pull'],
            cwd=repo_dir,
            capture_output=True,
            text=True,
            timeout=30
        )
        stdout = result.stdout.strip()
        stderr = result.stderr.strip()
        output = stdout or stderr or '(нет вывода)'

        # Ограничиваем длину
        if len(output) > 800:
            output = output[:800] + '...'

        # Автоматически добавляем новые категории в menu.json
        menu_cats_log = ''
        try:
            menu_data = load_menu()
            existing_ids = [c['id'] for c in menu_data['categories']]
            new_cats = [
                {"id": "detox_water", "name": "💧 Детокс вода", "type": "bar", "items": []},
                {"id": "detox_fresh", "name": "🥬 Детокс фреш", "type": "bar", "items": []},
                {"id": "immune_shot", "name": "⚡ Иммунный шот", "type": "bar", "items": []},
            ]
            added = []
            for cat in new_cats:
                if cat['id'] not in existing_ids:
                    menu_data['categories'].append(cat)
                    added.append(cat['name'])
            if added:
                save_menu(menu_data)
                menu_cats_log = f"✅ Добавлены категории: {', '.join(added)}\n"
            else:
                menu_cats_log = "✅ Категории меню актуальны\n"
        except Exception as me:
            menu_cats_log = f"⚠️ Ошибка обновления категорий: {me}\n"

        # Перезагружаем кеш меню
        menu_reloaded = False
        try:
            from handlers import menu as menu_handler
            menu_handler.reload_menu()
            menu_reloaded = True
        except Exception as e:
            pass

        if result.returncode == 0:
            status_icon = '✅'
            status_text = 'Успешно обновлено!'
        else:
            status_icon = '⚠️'
            status_text = f'Git вернул код {result.returncode}'

        menu_status = '✅ Кеш меню перезагружен' if menu_reloaded else '⚠️ Кеш меню не перезагружен'

        await query.message.edit_text(
            f"{status_icon} <b>git pull завершён</b>\n"
            f"{status_text}\n\n"
            f"<code>{output}</code>\n\n"
            f"{menu_cats_log}"
            f"{menu_status}",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Админ-панель", callback_data="adm_menu")]
            ])
        )

    except subprocess.TimeoutExpired:
        await query.message.edit_text(
            "⏱ <b>Таймаут!</b>\n\ngit pull выполнялся слишком долго (>30 сек).",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Назад", callback_data="adm_menu")]
            ])
        )
    except FileNotFoundError:
        await query.message.edit_text(
            "❌ <b>Git не найден</b>\n\nКоманда <code>git</code> недоступна на сервере.",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Назад", callback_data="adm_menu")]
            ])
        )
    except Exception as e:
        await query.message.edit_text(
            f"❌ <b>Ошибка:</b>\n<code>{str(e)}</code>",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Назад", callback_data="adm_menu")]
            ])
        )



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


# ─── Управление велком-буком ──────────────────────────────────

async def admin_welcome_mgmt_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Список разделов велком-бука."""
    query = update.callback_query
    if not is_admin(query.from_user):
        await query.answer("Нет доступа!")
        return
    await query.answer()

    data = load_welcome()
    sections = data.get('sections', [])

    text = "📖 <b>Управление велком-буком</b>\n\n"
    text += f"Разделов: <b>{len(sections)}</b>\n\n"

    buttons = []
    for i, section in enumerate(sections):
        title = section.get('title', f'Раздел {i+1}')
        buttons.append([
            InlineKeyboardButton(title, callback_data=f"adm_wsec_{i}"),
        ])

    buttons.append([InlineKeyboardButton("➕ Добавить раздел", callback_data="adm_wadd")])
    buttons.append([InlineKeyboardButton("🔙 Назад", callback_data="adm_menu")])

    await query.message.edit_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(buttons))


async def admin_welcome_section_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Действия с отдельным разделом."""
    query = update.callback_query
    if not is_admin(query.from_user):
        await query.answer("Нет доступа!")
        return
    await query.answer()

    idx = int(query.data.replace("adm_wsec_", ""))
    data = load_welcome()
    sections = data.get('sections', [])

    if idx >= len(sections):
        await query.answer("Раздел не найден")
        return

    section = sections[idx]
    title = section.get('title', '')
    content = section.get('content', '')
    preview = content[:200] + '...' if len(content) > 200 else content
    # Убираем HTML теги для превью
    import re
    preview_clean = re.sub(r'<[^>]+>', '', preview)

    text = (
        f"📖 <b>Раздел #{idx+1}</b>\n\n"
        f"<b>Заголовок:</b> {title}\n\n"
        f"<b>Превью:</b>\n{preview_clean}"
    )

    await query.message.edit_text(
        text,
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✏️ Изменить заголовок", callback_data=f"adm_wedit_title_{idx}"),
            ],
            [
                InlineKeyboardButton("✏️ Изменить содержание", callback_data=f"adm_wedit_content_{idx}"),
            ],
            [
                InlineKeyboardButton("🗑️ Удалить раздел", callback_data=f"adm_wdel_{idx}"),
            ],
            [
                InlineKeyboardButton("🔙 Назад", callback_data="adm_welcome_mgmt"),
            ],
        ])
    )


async def admin_welcome_edit_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начать редактирование заголовка или содержания."""
    query = update.callback_query
    if not is_admin(query.from_user):
        await query.answer("Нет доступа!")
        return
    await query.answer()

    # adm_wedit_title_0 или adm_wedit_content_0
    parts = query.data.split('_')
    field = parts[2]   # 'title' или 'content'
    idx = int(parts[3])

    context.user_data['awaiting_welcome'] = {
        'action': 'edit',
        'idx': idx,
        'field': field
    }

    if field == 'title':
        prompt = f"✉️ Напишите новый <b>заголовок</b> раздела (include emoji)."
    else:
        prompt = (
            f"✉️ Напишите новое <b>содержание</b> раздела.\n\n"
            f"💡 Можно использовать HTML: <b>жирный</b>, • для списков, emoji.\n"
            f"Для переноса строки используйте \\n.\n\n"
            f"/cancel — отмена"
        )

    await query.message.reply_text(prompt, parse_mode='HTML')


async def admin_welcome_delete_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Подтверждение удаления раздела."""
    query = update.callback_query
    if not is_admin(query.from_user):
        await query.answer("Нет доступа!")
        return
    await query.answer()

    idx = int(query.data.replace("adm_wdel_", ""))
    data = load_welcome()
    sections = data.get('sections', [])

    if idx >= len(sections):
        return

    title = sections[idx].get('title', f'Раздел {idx+1}')

    await query.message.edit_text(
        f"⚠️ <b>Удалить раздел?</b>\n\n«{title}»\n\nЭто действие нельзя отменить!",
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Да, удалить", callback_data=f"adm_wdelok_{idx}"),
                InlineKeyboardButton("❌ Отмена", callback_data=f"adm_wsec_{idx}"),
            ]
        ])
    )


async def admin_welcome_delete_ok_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Подтверждённое удаление."""
    query = update.callback_query
    if not is_admin(query.from_user):
        await query.answer("Нет доступа!")
        return
    await query.answer()

    idx = int(query.data.replace("adm_wdelok_", ""))
    data = load_welcome()
    sections = data.get('sections', [])

    if idx < len(sections):
        removed = sections.pop(idx)
        save_welcome(data)
        title = removed.get('title', 'Раздел')
        await query.message.edit_text(
            f"✅ Раздел <b>«{title}»</b> удалён.",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 К велком-буку", callback_data="adm_welcome_mgmt")]
            ])
        )


async def admin_welcome_add_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начать добавление нового раздела."""
    query = update.callback_query
    if not is_admin(query.from_user):
        await query.answer("Нет доступа!")
        return
    await query.answer()

    context.user_data['awaiting_welcome'] = {'action': 'add', 'step': 'title'}

    await query.message.reply_text(
        "➕ <b>Добавление нового раздела</b>\n\n"
        "Шаг 1/2: Напишите <b>заголовок</b> нового раздела (emoji + текст).\n"
        "Например: 📌 Новая тема\n\n/cancel — отмена",
        parse_mode='HTML'
    )


async def handle_admin_welcome_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка текста для велком-бука."""
    welcome_state = context.user_data.get('awaiting_welcome')
    if not welcome_state:
        return False

    text = update.message.text.strip()
    action = welcome_state['action']

    if action == 'edit':
        idx = welcome_state['idx']
        field = welcome_state['field']

        data = load_welcome()
        sections = data.get('sections', [])
        if idx < len(sections):
            sections[idx][field] = text
            save_welcome(data)
            field_name = "заголовок" if field == 'title' else "содержание"
            await update.message.reply_text(
                f"✅ {field_name.capitalize()} раздела обновлён!",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 К разделу", callback_data=f"adm_wsec_{idx}")],
                    [InlineKeyboardButton("📖 К велком-буку", callback_data="adm_welcome_mgmt")],
                ])
            )
        context.user_data.pop('awaiting_welcome', None)
        return True

    elif action == 'add':
        step = welcome_state.get('step')

        if step == 'title':
            context.user_data['awaiting_welcome']['title'] = text
            context.user_data['awaiting_welcome']['step'] = 'content'
            await update.message.reply_text(
                f"Чотово: заголовок <b>«{text}»</b>\n\n"
                f"Шаг 2/2: Напишите <b>содержание</b> раздела.\n"
                f"💡 Можно HTML: <b>жирный</b>, • для списков.\n\n/cancel — отмена",
                parse_mode='HTML'
            )
            return True

        elif step == 'content':
            title = welcome_state.get('title', 'Новый раздел')
            data = load_welcome()
            sections = data.setdefault('sections', [])

            import uuid
            new_section = {
                "id": f"section_{uuid.uuid4().hex[:8]}",
                "title": title,
                "content": text
            }
            sections.append(new_section)
            save_welcome(data)

            context.user_data.pop('awaiting_welcome', None)
            await update.message.reply_text(
                f"✅ Новый раздел <b>«{title}»</b> успешно добавлен!",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📖 К велком-буку", callback_data="adm_welcome_mgmt")],
                ])
            )
            return True

    return False



# ─── Управление экскурсией (Видео) ────────────────────────────────

def load_tour():
    path = os.path.join(DATA_DIR, 'tour.json')
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {"title": "Экскурсия", "videos": []}

def save_tour(data):
    path = os.path.join(DATA_DIR, 'tour.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

async def admin_tour_mgmt_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not is_admin(query.from_user): return
    await query.answer()

    data = load_tour()
    videos = data.get('videos', [])

    text = "🎬 <b>Управление экскурсией</b>\n\nЗдесь вы можете управлять видео для новых сотрудников.\n\n"
    
    if not videos:
        text += "<i>Пока нет ни одного видео.</i>"
    else:
        text += "<b>Текущие видео:</b>"

    buttons = []
    for idx, v in enumerate(videos):
        buttons.append([InlineKeyboardButton(f"{v.get('title', 'Видео')} ({v.get('type', 'youtube')})", callback_data=f"adm_tsec_{v['id']}")])
    
    buttons.append([InlineKeyboardButton("➕ Добавить YouTube видео", callback_data="adm_tadd")])
    buttons.append([InlineKeyboardButton("🔙 В меню", callback_data="adm_menu")])

    await query.message.edit_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(buttons))

async def admin_tour_video_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not is_admin(query.from_user): return
    await query.answer()

    vid = int(query.data.replace("adm_tsec_", ""))
    data = load_tour()
    video = next((v for v in data.get('videos', []) if v['id'] == vid), None)
    
    if not video:
        await query.answer("Видео не найдено")
        return

    text = f"🎬 <b>Видео:</b> {video.get('title')}\n"
    text += f"<b>Описание:</b> {video.get('description', '')}\n"
    text += f"<b>Тип:</b> {video.get('type')}\n"
    if video.get('type') == 'youtube':
        text += f"<b>ID:</b> <code>{video.get('youtube_id')}</code>\n"

    buttons = [
        [InlineKeyboardButton("🗑️ Удалить", callback_data=f"adm_tdel_{vid}")],
        [InlineKeyboardButton("🔙 Назад", callback_data="adm_tour_mgmt")]
    ]
    await query.message.edit_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(buttons))

async def admin_tour_delete_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not is_admin(query.from_user): return
    await query.answer()

    vid = int(query.data.replace("adm_tdel_", ""))
    buttons = [
        [InlineKeyboardButton("✅ ДА, удалить", callback_data=f"adm_tdelok_{vid}")],
        [InlineKeyboardButton("❌ Отмена", callback_data=f"adm_tsec_{vid}")]
    ]
    await query.message.edit_text("Вы точно хотите удалить это видео из экскурсии?", reply_markup=InlineKeyboardMarkup(buttons))

async def admin_tour_delete_ok_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not is_admin(query.from_user): return
    await query.answer()

    vid = int(query.data.replace("adm_tdelok_", ""))
    data = load_tour()
    data['videos'] = [v for v in data.get('videos', []) if v['id'] != vid]
    save_tour(data)

    await query.message.edit_text(
        "✅ Видео удалено.",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 К списку", callback_data="adm_tour_mgmt")]])
    )

async def admin_tour_add_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not is_admin(query.from_user): return
    await query.answer()

    context.user_data['awaiting_tour'] = {'step': 'url'}
    
    await query.message.reply_text(
        "🎬 <b>Добавление YouTube видео</b>\n\n"
        "Отправьте мне <b>ссылку на видео YouTube</b> (например: https://youtu.be/dQw4w9WgXcQ).\n"
        "<i>Желательно загружать как «Доступ по ссылке».</i>\n\n"
        "/cancel — отмена",
        parse_mode='HTML'
    )

async def handle_admin_tour_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if not context.user_data.get('awaiting_tour'): return False
    
    step = context.user_data['awaiting_tour']['step']
    text = update.message.text.strip()
    
    if step == 'url':
        import re
        yt_regex = r'(?:youtube\.com\/(?:[^\/]+\/.+\/|(?:v|e(?:mbed)?)\/|.*[?&]v=)|youtu\.be\/)([^"&?\/\s]{11})'
        match = re.search(yt_regex, text)
        if not match:
            await update.message.reply_text("❌ Не смог найти YouTube ID в ссылке. Попробуйте отправить прямую ссылку (например https://youtu.be/xxx) или /cancel")
            return True
            
        yt_id = match.group(1)
        context.user_data['awaiting_tour'] = {'step': 'title', 'yt_id': yt_id}
        await update.message.reply_text(
            f"✅ Ссылка принята (ID: {yt_id}).\n\n"
            "Теперь отправьте <b>название</b> видео (например «Знакомство с залом»):",
            parse_mode='HTML'
        )
        return True
        
    elif step == 'title':
        context.user_data['awaiting_tour']['title'] = text
        context.user_data['awaiting_tour']['step'] = 'desc'
        await update.message.reply_text(
            "Отлично. Теперь отправьте короткое <b>описание</b> (о чем это видео):"
        )
        return True
        
    elif step == 'desc':
        desc = text
        state = context.user_data['awaiting_tour']
        yt_id = state['yt_id']
        title = state['title']
        
        data = load_tour()
        videos = data.setdefault('videos', [])
        new_id = max([v.get('id', 0) for v in videos] + [0]) + 1
        
        videos.append({
            "id": new_id,
            "title": title,
            "description": desc,
            "type": "youtube",
            "url": f"https://www.youtube.com/watch?v={yt_id}",
            "youtube_id": yt_id
        })
        save_tour(data)
        
        context.user_data.pop('awaiting_tour', None)
        await update.message.reply_text(
            f"✅ Видео <b>«{title}»</b> добавлено в экскурсию!",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🎬 К экскурсии", callback_data="adm_tour_mgmt")]])
        )
        return True

    return False

# ─── Управление администраторами ─────────────────────────────────

async def admin_admins_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Список администраторов с кнопками управления."""
    query = update.callback_query
    if not is_superadmin(query.from_user):
        await query.answer("Только суперадмин!")
        return
    await query.answer()
    context.user_data.pop('awaiting_add_admin', None)

    admins = db.get_db_admins()

    text = "🔑 <b>Администраторы</b>\n\n"
    text += f"<b>Суперадмин:</b> @{ADMIN_USERNAME or '—'}\n\n"

    buttons = []
    if admins:
        text += f"<b>Добавленные ({len(admins)}):</b>\n"
        for a in admins:
            name = a.get('first_name') or f"ID {a['user_id']}"
            uname = f"@{a['username']}" if a.get('username') else ''
            role_label = ROLE_NAMES.get(a.get('role', 'full'), '👑 Полный')
            text += f"• {name} {uname} — {role_label}\n"
            buttons.append([
                InlineKeyboardButton(
                    f"🗑 {name} ({role_label})",
                    callback_data=f"adm_rmadm_{a['user_id']}"
                )
            ])
    else:
        text += "<i>Дополнительных администраторов нет.</i>"

    buttons.append([InlineKeyboardButton("➕ Добавить администратора", callback_data="adm_addadm")])
    buttons.append([InlineKeyboardButton("🔙 Назад", callback_data="adm_menu")])

    await query.message.edit_text(
        text, parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(buttons)
    )


async def admin_add_admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать список пользователей для выбора нового админа."""
    query = update.callback_query
    if not is_superadmin(query.from_user):
        await query.answer("Только суперадмин!")
        return
    await query.answer()

    users = db.get_non_admin_users(limit=30)

    if not users:
        await query.message.edit_text(
            "👥 <b>Нет доступных пользователей</b>\n\n"
            "Все зарегистрированные пользователи уже являются администраторами,\n"
            "или ещё никто не написал /start боту.",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Назад", callback_data="adm_admins")]
            ])
        )
        return

    text = "👤 <b>Выбери пользователя</b>\n\nКого назначить администратором?\n\n"
    buttons = []
    for u in users:
        name = u.get('first_name') or f"ID {u['user_id']}"
        uname = f" @{u['username']}" if u.get('username') else ''
        buttons.append([
            InlineKeyboardButton(
                f"{name}{uname}",
                callback_data=f"adm_pickusr_{u['user_id']}"
            )
        ])
    buttons.append([InlineKeyboardButton("🔙 Назад", callback_data="adm_admins")])

    await query.message.edit_text(
        text, parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(buttons)
    )


async def admin_pick_user_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Пользователь выбран — выбрать роль."""
    query = update.callback_query
    if not is_superadmin(query.from_user):
        await query.answer("Только суперадмин!")
        return
    await query.answer()

    user_id = int(query.data.replace("adm_pickusr_", ""))

    # Ищем пользователя в БД
    conn = db.get_connection()
    c = conn.cursor()
    c.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    row = c.fetchone()
    conn.close()

    if not row:
        await query.answer("Пользователь не найден!")
        return

    row = dict(row)
    name = row.get('first_name') or f"ID {user_id}"
    uname = f" @{row['username']}" if row.get('username') else ''

    await query.message.edit_text(
        f"👤 <b>{name}{uname}</b>\n\n"
        "Выбери <b>уровень доступа</b>:\n\n"
        "👑 <b>Полный доступ</b> — статистика, пользователи, награды, рассылка, меню, велком-бук, экскурсия, смены\n\n"
        "📝 <b>Контент</b> — только меню, велком-бук и экскурсия",
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("👑 Полный доступ", callback_data=f"adm_setrole_full_{user_id}")],
            [InlineKeyboardButton("📝 Контент (меню + велком)", callback_data=f"adm_setrole_content_{user_id}")],
            [InlineKeyboardButton("❌ Отмена", callback_data="adm_admins")],
        ])
    )


async def admin_set_role_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Установить роль и добавить администратора."""
    query = update.callback_query
    if not is_superadmin(query.from_user):
        await query.answer("Только суперадмин!")
        return
    await query.answer()

    parts = query.data.replace("adm_setrole_", "").split("_", 1)
    role = parts[0]
    user_id = int(parts[1])

    # Получаем данные пользователя
    conn = db.get_connection()
    c = conn.cursor()
    c.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    row = c.fetchone()
    conn.close()

    if not row:
        await query.answer("Пользователь не найден!")
        return

    row = dict(row)
    username = row.get('username') or ''
    first_name = row.get('first_name') or ''
    name = first_name or f"ID {user_id}"
    uname = f" @{username}" if username else ''

    added = db.add_db_admin(
        user_id=user_id,
        username=username,
        first_name=first_name,
        added_by=query.from_user.id,
        role=role
    )

    role_label = ROLE_NAMES.get(role, role)

    if added:
        await query.message.edit_text(
            f"✅ <b>{name}{uname}</b> назначен администратором!\n\n"
            f"Роль: {role_label}\n"
            f"Теперь он может войти в /admin",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 К администраторам", callback_data="adm_admins")]
            ])
        )
    else:
        await query.message.edit_text(
            f"ℹ️ <b>{name}{uname}</b> уже является администратором.",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 К администраторам", callback_data="adm_admins")]
            ])
        )


async def admin_remove_admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Подтверждение удаления администратора."""
    query = update.callback_query
    if not is_superadmin(query.from_user):
        await query.answer("Только суперадмин!")
        return
    await query.answer()

    target_id = int(query.data.replace("adm_rmadm_", ""))

    admins = db.get_db_admins()
    target = next((a for a in admins if a['user_id'] == target_id), None)
    if not target:
        await query.answer("Не найден!")
        return

    name = target.get('first_name') or f"ID {target_id}"
    uname = f" @{target['username']}" if target.get('username') else ''
    role_label = ROLE_NAMES.get(target.get('role', 'full'), '?')

    await query.message.edit_text(
        f"⚠️ <b>Убрать администратора?</b>\n\n"
        f"👤 {name}{uname}\n"
        f"Роль: {role_label}\n\n"
        f"После удаления он потеряет доступ к /admin.",
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Да, удалить", callback_data=f"adm_rmadm_ok_{target_id}"),
                InlineKeyboardButton("❌ Отмена", callback_data="adm_admins"),
            ]
        ])
    )


async def admin_confirm_remove_admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Подтверждённое удаление администратора."""
    query = update.callback_query
    if not is_superadmin(query.from_user):
        await query.answer("Только суперадмин!")
        return
    await query.answer()

    target_id = int(query.data.replace("adm_rmadm_ok_", ""))
    removed = db.remove_db_admin(target_id)

    if removed:
        await query.message.edit_text(
            "✅ Администратор успешно удалён.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 К администраторам", callback_data="adm_admins")]
            ])
        )
    else:
        await query.answer("Пользователь не найден в списке.")


def get_handlers():
    return [
        CommandHandler("admin", admin_command),
        CommandHandler("cancel", cancel_command),
        CallbackQueryHandler(admin_gitpull_callback, pattern="^adm_gitpull$"),
        CallbackQueryHandler(admin_menu_callback, pattern="^adm_menu$"),
        CallbackQueryHandler(admin_stats_callback, pattern="^adm_stats$"),
        CallbackQueryHandler(admin_users_callback, pattern="^adm_users$"),
        CallbackQueryHandler(admin_rewards_callback, pattern="^adm_rewards$"),
        CallbackQueryHandler(admin_confirm_reward_callback, pattern="^adm_cr_"),
        CallbackQueryHandler(admin_reject_reward_callback, pattern="^adm_rr_"),
        CallbackQueryHandler(admin_broadcast_callback, pattern="^adm_bcast$"),
        CallbackQueryHandler(admin_attendance_callback, pattern="^adm_attendance$"),
        # ── Управление меню ──
        CallbackQueryHandler(admin_menu_mgmt_callback, pattern="^adm_menu_mgmt$"),
        CallbackQueryHandler(admin_menu_cat_callback, pattern="^adm_mcat_"),
        CallbackQueryHandler(admin_menu_items_callback, pattern="^adm_mitem_"),
        CallbackQueryHandler(admin_delete_item_callback, pattern="^adm_del_"),
        CallbackQueryHandler(admin_delete_item_ok_callback, pattern="^adm_delok_"),
        CallbackQueryHandler(admin_edit_item_callback, pattern="^adm_edit_"),
        CallbackQueryHandler(admin_edit_field_callback, pattern="^adm_edf_"),
        CallbackQueryHandler(admin_add_item_callback, pattern="^adm_add_"),
        # ── Управление квизом ──
        CallbackQueryHandler(admin_quiz_mgmt_callback, pattern="^adm_quiz_mgmt$"),
        CallbackQueryHandler(admin_quiz_list_callback, pattern="^adm_quiz_list_"),
        CallbackQueryHandler(admin_quiz_add_callback, pattern="^adm_quiz_add$"),
        CallbackQueryHandler(admin_quiz_cost_callback, pattern="^adm_quiz_cost$"),
        CallbackQueryHandler(admin_quiz_del_callback, pattern="^adm_qdel_"),
        # ── Управление велком-буком ──
        CallbackQueryHandler(admin_welcome_mgmt_callback, pattern="^adm_welcome_mgmt$"),
        CallbackQueryHandler(admin_welcome_section_callback, pattern="^adm_wsec_"),
        CallbackQueryHandler(admin_welcome_edit_callback, pattern="^adm_wedit_"),
        CallbackQueryHandler(admin_welcome_delete_callback, pattern="^adm_wdel_"),
        CallbackQueryHandler(admin_welcome_delete_ok_callback, pattern="^adm_wdelok_"),
        CallbackQueryHandler(admin_welcome_add_callback, pattern="^adm_wadd$"),
        # ── Управление экскурсией ──
        CallbackQueryHandler(admin_tour_mgmt_callback, pattern="^adm_tour_mgmt$"),
        CallbackQueryHandler(admin_tour_video_callback, pattern="^adm_tsec_"),
        CallbackQueryHandler(admin_tour_delete_callback, pattern="^adm_tdel_"),
        CallbackQueryHandler(admin_tour_delete_ok_callback, pattern="^adm_tdelok_"),
        CallbackQueryHandler(admin_tour_add_callback, pattern="^adm_tadd$"),
        # ── Управление администраторами ──
        CallbackQueryHandler(admin_admins_callback, pattern="^adm_admins$"),
        CallbackQueryHandler(admin_add_admin_callback, pattern="^adm_addadm$"),
        CallbackQueryHandler(admin_pick_user_callback, pattern="^adm_pickusr_"),
        CallbackQueryHandler(admin_set_role_callback, pattern="^adm_setrole_"),
        CallbackQueryHandler(admin_confirm_remove_admin_callback, pattern="^adm_rmadm_ok_"),
        CallbackQueryHandler(admin_remove_admin_callback, pattern="^adm_rmadm_"),
        # Текстовые ответы и фото (должен быть последним!)
        MessageHandler((filters.TEXT | filters.PHOTO) & ~filters.COMMAND, handle_admin_text),
    ]

