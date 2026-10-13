"""Обработчик админ-панели с управлением меню."""
import subprocess
import json
import os
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters
import database as db
from config import ADMIN_ID, ADMIN_USERNAME, DATA_DIR


def format_price(price):
    """115000 → «115 000 сум»; пусто, если цена не задана."""
    if not price:
        return '—'
    return f"{int(price):,}".replace(',', ' ') + ' сум'


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


def load_trainings():
    path = os.path.join(DATA_DIR, 'trainings.json')
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"trainings": []}


def save_trainings(data):
    path = os.path.join(DATA_DIR, 'trainings.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


def load_events():
    path = os.path.join(DATA_DIR, 'events.json')
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"events": []}


def save_events(data):
    path = os.path.join(DATA_DIR, 'events.json')
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
    section: 'stats','users','rewards','broadcast','menu','welcome','tour','trainings','events','attendance','admins','gitpull'
    """
    role = get_user_role(user)
    if role == 'superadmin':
        return True
    if role == 'full':
        return section != 'admins'  # полный доступ везде кроме управления админами
    if role == 'content':
        return section in ('menu', 'welcome', 'tour', 'trainings', 'events')
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
        InlineKeyboardButton("🎓 Тренинги", callback_data="adm_trainings_mgmt"),
    ])
    buttons.append([
        InlineKeyboardButton("📅 События", callback_data="adm_events_mgmt"),
    ])
    if role == 'superadmin':
        buttons.append([
            InlineKeyboardButton("🔑 Администраторы", callback_data="adm_admins"),
        ])
        buttons.append([
            InlineKeyboardButton("⚙️ Настройки бота", callback_data="adm_settings"),
            InlineKeyboardButton("🔄 Обновить код", callback_data="adm_gitpull"),
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
        f"<b>Цена:</b> {format_price(item.get('price'))}\n"
        f"<b>КБЖУ:</b> {item.get('calories', 0)}/{item.get('protein', 0)}/{item.get('fat', 0)}/{item.get('carbs', 0)}\n"
        f"<b>Аллергены:</b> {item.get('allergens', '—')}\n"
        f"<b>Время готовки:</b> {item.get('prep_time', '—')}\n"
        f"<b>Аудио-гид:</b> {'Есть 🎙' if item.get('audio') else 'Нет'}\n"
        f"<b>Хит продаж:</b> {'Да 🔥' if item.get('is_hit') else 'Нет'}\n"
        f"<b>Видно гостям:</b> {'Нет 🙈' if item.get('hidden_from_guest') else 'Да'}\n\n"
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
            InlineKeyboardButton("⏱ Время готовки", callback_data=f"adm_edf_prep_{cat_id}_{item_idx}"),
            InlineKeyboardButton("🎙 Аудио-гид", callback_data=f"adm_edf_audio_{cat_id}_{item_idx}")
        ],
        [InlineKeyboardButton("💰 Цена", callback_data=f"adm_edf_price_{cat_id}_{item_idx}")],
        [
            InlineKeyboardButton(
                f"🙈 Видно гостям: {'Нет' if item.get('hidden_from_guest') else 'Да'}",
                callback_data=f"adm_edf_guest_{cat_id}_{item_idx}"
            )
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

    if field in ('hit', 'guest'):
        context.user_data['awaiting_edit'] = False
        data = load_menu()
        category = next((c for c in data['categories'] if c['id'] == cat_id), None)
        if category and item_idx < len(category['items']):
            item = category['items'][item_idx]
            if field == 'hit':
                item['is_hit'] = not item.get('is_hit', False)
            else:
                item['hidden_from_guest'] = not item.get('hidden_from_guest', False)
            save_menu(data)

            # Рендерим обновленную карточку сразу
            text = (
                f"✏️ <b>Редактирование блюда</b>\n\n"
                f"<b>Название:</b> {item.get('name', '—')}\n"
                f"<b>Описание:</b> {item.get('description', '—')}\n"
                f"<b>Состав:</b> {item.get('ingredients', '—')}\n"
                f"<b>Объём:</b> {item.get('volume', '—')}\n"
                f"<b>Цена:</b> {format_price(item.get('price'))}\n"
                f"<b>КБЖУ:</b> {item.get('calories', 0)}/{item.get('protein', 0)}/{item.get('fat', 0)}/{item.get('carbs', 0)}\n"
                f"<b>Аллергены:</b> {item.get('allergens', '—')}\n"
                f"<b>Время готовки:</b> {item.get('prep_time', '—')}\n"
                f"<b>Хит продаж:</b> {'Да 🔥' if item.get('is_hit') else 'Нет'}\n"
                f"<b>Видно гостям:</b> {'Нет 🙈' if item.get('hidden_from_guest') else 'Да'}\n\n"
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
                [InlineKeyboardButton("💰 Цена", callback_data=f"adm_edf_price_{cat_id}_{item_idx}")],
                [
                    InlineKeyboardButton(
                        f"🙈 Видно гостям: {'Нет' if item.get('hidden_from_guest') else 'Да'}",
                        callback_data=f"adm_edf_guest_{cat_id}_{item_idx}"
                    )
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
    elif field == 'price':
        prompt = "Отправь новую <b>Цену</b> в сумах (только число, например: <code>115000</code>).\nДля удаления отправь <code>-</code>.\nИли /cancel для отмены."
    elif field == 'audio':
        prompt = "Отправь <b>Аудио-гид</b> (голосовое сообщение или mp3/ogg файл) для этого блюда.\nДля удаления отправь <code>-</code>.\nИли /cancel для отмены."

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
    
    # Игнорируем сообщения из групп (например, если админ просто пишет в рабочий чат)
    if update.message.chat.type != 'private':
        return

    text = update.message.text.strip() if update.message.text else ""
    photo = update.message.photo[-1] if update.message.photo else None

    # ── Настройки ──
    if context.user_data.get('awaiting_setting'):
        setting_key = context.user_data.pop('awaiting_setting')
        if text == '/cancel':
            await update.message.reply_text("❌ Отменено.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 В настройки", callback_data="adm_settings")]]))
            return True
            
        key_map = {
            'ptscorr': 'points_correct',
            'ptswrong': 'points_wrong',
            'chatid': 'chat_id'
        }

        real_key = key_map.get(setting_key)
        if real_key:
            if real_key == 'chat_id':
                # ID группы/канала — число (обычно отрицательное, у супергрупп с -100…)
                # либо @username публичного канала/группы. Отклоняем любой другой текст,
                # чтобы случайное сообщение не затёрло рабочий chat_id (как уже было).
                candidate = text
                is_valid = bool(re.fullmatch(r'-?\d+', candidate)) or bool(re.fullmatch(r'@[A-Za-z0-9_]{5,32}', candidate))
                if not is_valid:
                    context.user_data['awaiting_setting'] = setting_key
                    await update.message.reply_text(
                        "❌ Это не похоже на ID чата. Нужно число (например: -1001234567890) "
                        "или @username канала/группы.\n\nПришли корректный ID или /cancel.",
                    )
                    return True
                val = candidate
            else:
                try:
                    val = int(text)
                except ValueError:
                    context.user_data['awaiting_setting'] = setting_key
                    await update.message.reply_text("❌ Нужно отправить число. Попробуй ещё раз или /cancel.")
                    return True
            save_settings_val(real_key, val)
            await update.message.reply_text(f"✅ Настройка {real_key} сохранена: {val}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 В настройки", callback_data="adm_settings")]]))
        return True

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

    # ── Тренинги ──
    if context.user_data.get('awaiting_training'):
        handled = await handle_admin_training_text(update, context)
        if handled:
            return

    # ── События ──
    if context.user_data.get('awaiting_event'):
        handled = await handle_admin_event_text(update, context)
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
        elif field == 'price':
            if text == "-":
                item.pop('price', None)
            else:
                digits = re.sub(r'\D', '', text or '')
                if not digits:
                    await update.message.reply_text("❌ Нужно отправить число, например: 115000")
                    return
                item['price'] = int(digits)
        elif field == 'prep':
            if not text:
                await update.message.reply_text("❌ Нужно отправить текст.")
                return
            item['prep_time'] = "" if text == "-" else text
        elif field == 'audio':
            audio_obj = update.message.voice or update.message.audio
            if text == "-":
                item['audio'] = ""
            elif audio_obj:
                import uuid
                from config import AUDIO_DIR
                os.makedirs(AUDIO_DIR, exist_ok=True)
                ext = "ogg" if update.message.voice else "mp3" 
                filename = f"audio_{uuid.uuid4().hex[:8]}.{ext}"
                audio_path = os.path.join(AUDIO_DIR, filename)
                new_file = await audio_obj.get_file()
                await new_file.download_to_drive(custom_path=audio_path)
                item['audio'] = filename
            else:
                await update.message.reply_text("❌ Отправь голосовое сообщение (voice/audio) или ` - ` для удаления.", parse_mode='Markdown')
                return
                
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


async def admin_settings_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not is_superadmin(query.from_user):
        await query.answer("Нет доступа!")
        return
    await query.answer()

    from config import get_settings
    s = get_settings()
    
    text = (
        f"⚙️ <b>Настройки бота</b>\n\n"
        f"🔹 Стоимость напитка: <b>{s.get('points_for_drink', 100)}</b>\n"
        f"🔹 Балл за верный ответ (квиз): <b>{s.get('points_correct', 1)}</b>\n"
        f"🔹 Штраф за ошибку (квиз): <b>{s.get('points_wrong', -2)}</b>\n"
        f"🔹 Кулдаун квиза (часов): <b>{s.get('quiz_cooldown_hours', 24)}</b>\n"
        f"🔹 Рабочий чат ID: <b>{s.get('chat_id', 'Не задан')}</b>\n\n"
        f"Что изменить?"
    )
    buttons = [
        [InlineKeyboardButton("Балл за верный ответ", callback_data="adm_set_ptscorr")],
        [InlineKeyboardButton("Штраф за ошибку", callback_data="adm_set_ptswrong")],
        [InlineKeyboardButton("Рабочий чат (ID)", callback_data="adm_set_chatid")],
        [InlineKeyboardButton("📢 Тест факта дня", callback_data="adm_test_fact")],
        [InlineKeyboardButton("📢 Тест напоминаний о событиях", callback_data="adm_test_events")],
        [InlineKeyboardButton("🔙 Назад", callback_data="adm_menu")]
    ]
    await query.message.edit_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(buttons))

async def admin_set_setting_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not is_superadmin(query.from_user):
        await query.answer("Нет доступа!")
        return
    await query.answer()
    
    setting_key = query.data.replace('adm_set_', '')
    context.user_data['awaiting_setting'] = setting_key
    
    await query.message.edit_text(
        f"⚙️ <b>Изменение настройки {setting_key}</b>\n\n"
        "Введите новое значение текстом (например: <code>-100123456789</code> или <code>2</code>).\n"
        "Для отмены введите /cancel",
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="adm_settings")]])
    )

async def admin_test_fact_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not is_superadmin(query.from_user):
        await query.answer("Нет доступа!")
        return
    await query.answer("Запускаем тест...")

    import publisher
    await publisher.send_random_fact(context)
    await query.message.reply_text("✅ Рассылка протестирована! Проверь рабочий чат.")


async def admin_test_events_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not is_superadmin(query.from_user):
        await query.answer("Нет доступа!")
        return
    await query.answer("Запускаем тест...")

    import publisher
    sent = await publisher.send_event_reminders(context)
    if sent:
        await query.message.reply_text(f"✅ Отправлено напоминаний: {sent}. Проверь рабочий чат.")
    else:
        await query.message.reply_text(
            "ℹ️ На завтра событий не найдено (или не задан рабочий чат) — отправлять было нечего."
        )


# ─── Управление тренингами ────────────────────────────────────────

async def admin_trainings_mgmt_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Список тренингов."""
    query = update.callback_query
    if not is_admin(query.from_user):
        await query.answer("Нет доступа!")
        return
    await query.answer()

    data = load_trainings()
    trainings = data.get('trainings', [])

    text = "🎓 <b>Управление тренингами</b>\n\n"
    text += f"Тренингов: <b>{len(trainings)}</b>\n\n"
    text += "Тренинг — это обучающий материал с несколькими модулями, который сотрудник проходит в мини-приложении."

    buttons = []
    for i, tr in enumerate(trainings):
        emoji = tr.get('emoji', '🎓')
        title = tr.get('title', f'Тренинг {i+1}')
        buttons.append([InlineKeyboardButton(f"{emoji} {title}", callback_data=f"adm_tr_{i}")])

    buttons.append([InlineKeyboardButton("➕ Добавить тренинг", callback_data="adm_tradd")])
    buttons.append([InlineKeyboardButton("🔙 Назад", callback_data="adm_menu")])

    await query.message.edit_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(buttons))


async def admin_training_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Карточка тренинга: список модулей + действия."""
    query = update.callback_query
    if not is_admin(query.from_user):
        await query.answer("Нет доступа!")
        return
    await query.answer()

    tidx = int(query.data.replace("adm_tr_", ""))
    data = load_trainings()
    trainings = data.get('trainings', [])
    if tidx >= len(trainings):
        await query.answer("Тренинг не найден")
        return

    training = trainings[tidx]
    modules = training.get('modules', [])

    text = (
        f"{training.get('emoji', '🎓')} <b>{training.get('title', '')}</b>\n"
        f"<i>{training.get('subtitle', '')}</i>\n\n"
        f"Модулей: <b>{len(modules)}</b>\n\n"
        f"Выбери модуль для редактирования или добавь новый:"
    )

    buttons = []
    for mi, m in enumerate(modules):
        mtitle = m.get('title', f'Модуль {mi+1}')
        short = mtitle[:32] + '…' if len(mtitle) > 32 else mtitle
        buttons.append([InlineKeyboardButton(f"📄 {short}", callback_data=f"adm_trmod_{tidx}_{mi}")])

    buttons.append([InlineKeyboardButton("➕ Добавить модуль", callback_data=f"adm_trmodadd_{tidx}")])
    buttons.append([
        InlineKeyboardButton("✏️ Название", callback_data=f"adm_tredit_title_{tidx}"),
        InlineKeyboardButton("✏️ Подзаголовок", callback_data=f"adm_tredit_subtitle_{tidx}"),
    ])
    buttons.append([
        InlineKeyboardButton("✏️ Эмодзи", callback_data=f"adm_tredit_emoji_{tidx}"),
        InlineKeyboardButton("🗑️ Удалить тренинг", callback_data=f"adm_trdel_{tidx}"),
    ])
    buttons.append([InlineKeyboardButton("🔙 К тренингам", callback_data="adm_trainings_mgmt")])

    await query.message.edit_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(buttons))


async def admin_training_add_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начать добавление нового тренинга."""
    query = update.callback_query
    if not is_admin(query.from_user):
        await query.answer("Нет доступа!")
        return
    await query.answer()

    context.user_data['awaiting_training'] = {'action': 'add_training', 'step': 'emoji'}

    await query.message.reply_text(
        "➕ <b>Новый тренинг</b>\n\n"
        "Шаг 1/3: Пришли <b>эмодзи</b> для тренинга (например: 💬).\n\n/cancel — отмена",
        parse_mode='HTML'
    )


async def admin_training_edit_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начать редактирование поля тренинга (title/subtitle/emoji)."""
    query = update.callback_query
    if not is_admin(query.from_user):
        await query.answer("Нет доступа!")
        return
    await query.answer()

    # adm_tredit_title_0 / adm_tredit_subtitle_0 / adm_tredit_emoji_0
    parts = query.data.replace("adm_tredit_", "").rsplit("_", 1)
    field = parts[0]
    tidx = int(parts[1])

    context.user_data['awaiting_training'] = {'action': 'edit_training', 'field': field, 'tidx': tidx}

    field_names = {'title': 'название', 'subtitle': 'подзаголовок', 'emoji': 'эмодзи'}
    await query.message.reply_text(
        f"✉️ Пришли новое значение поля «{field_names.get(field, field)}».\n\n/cancel — отмена",
        parse_mode='HTML'
    )


async def admin_training_delete_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Подтверждение удаления тренинга."""
    query = update.callback_query
    if not is_admin(query.from_user):
        await query.answer("Нет доступа!")
        return
    await query.answer()

    tidx = int(query.data.replace("adm_trdel_", ""))
    data = load_trainings()
    trainings = data.get('trainings', [])
    if tidx >= len(trainings):
        return

    title = trainings[tidx].get('title', f'Тренинг {tidx+1}')
    await query.message.edit_text(
        f"⚠️ <b>Удалить тренинг?</b>\n\n«{title}»\n\nВсе его модули будут удалены. Это действие нельзя отменить!",
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Да, удалить", callback_data=f"adm_trdelok_{tidx}"),
                InlineKeyboardButton("❌ Отмена", callback_data=f"adm_tr_{tidx}"),
            ]
        ])
    )


async def admin_training_delete_ok_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Подтверждённое удаление тренинга."""
    query = update.callback_query
    if not is_admin(query.from_user):
        await query.answer("Нет доступа!")
        return
    await query.answer()

    tidx = int(query.data.replace("adm_trdelok_", ""))
    data = load_trainings()
    trainings = data.get('trainings', [])
    if tidx < len(trainings):
        removed = trainings.pop(tidx)
        save_trainings(data)
        await query.message.edit_text(
            f"✅ Тренинг <b>«{removed.get('title', '')}»</b> удалён.",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 К тренингам", callback_data="adm_trainings_mgmt")]
            ])
        )


async def admin_training_module_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Карточка модуля тренинга."""
    query = update.callback_query
    if not is_admin(query.from_user):
        await query.answer("Нет доступа!")
        return
    await query.answer()

    tidx_str, midx_str = query.data.replace("adm_trmod_", "").split("_")
    tidx, midx = int(tidx_str), int(midx_str)

    data = load_trainings()
    trainings = data.get('trainings', [])
    if tidx >= len(trainings) or midx >= len(trainings[tidx].get('modules', [])):
        await query.answer("Модуль не найден")
        return

    module = trainings[tidx]['modules'][midx]
    content = module.get('content', '')
    preview = re.sub(r'<[^>]+>', ' ', content)
    preview = re.sub(r'\s+', ' ', preview).strip()
    if len(preview) > 250:
        preview = preview[:250] + '...'

    text = (
        f"📄 <b>Модуль #{midx+1}</b>\n\n"
        f"<b>Заголовок:</b> {module.get('title', '')}\n\n"
        f"<b>Превью содержания:</b>\n{preview}"
    )

    await query.message.edit_text(
        text,
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✏️ Изменить заголовок", callback_data=f"adm_trmedit_title_{tidx}_{midx}")],
            [InlineKeyboardButton("✏️ Изменить содержание", callback_data=f"adm_trmedit_content_{tidx}_{midx}")],
            [InlineKeyboardButton("🗑️ Удалить модуль", callback_data=f"adm_trmdel_{tidx}_{midx}")],
            [InlineKeyboardButton("🔙 Назад", callback_data=f"adm_tr_{tidx}")],
        ])
    )


async def admin_training_module_edit_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начать редактирование заголовка/содержания модуля."""
    query = update.callback_query
    if not is_admin(query.from_user):
        await query.answer("Нет доступа!")
        return
    await query.answer()

    # adm_trmedit_title_0_1 / adm_trmedit_content_0_1
    rest = query.data.replace("adm_trmedit_", "")
    field, tidx_str, midx_str = rest.split("_")
    tidx, midx = int(tidx_str), int(midx_str)

    context.user_data['awaiting_training'] = {
        'action': 'edit_module', 'field': field, 'tidx': tidx, 'midx': midx
    }

    if field == 'title':
        prompt = "✉️ Пришли новый <b>заголовок</b> модуля (например: 3. Скрипты для кассиров)."
    else:
        prompt = (
            "✉️ Пришли новое <b>содержание</b> модуля.\n\n"
            "💡 Можно использовать простой HTML: &lt;b&gt;жирный&lt;/b&gt;, "
            "&lt;p&gt;абзац&lt;/p&gt;, &lt;ul&gt;&lt;li&gt;список&lt;/li&gt;&lt;/ul&gt;.\n\n"
            "/cancel — отмена"
        )

    await query.message.reply_text(prompt, parse_mode='HTML')


async def admin_training_module_add_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начать добавление модуля в тренинг."""
    query = update.callback_query
    if not is_admin(query.from_user):
        await query.answer("Нет доступа!")
        return
    await query.answer()

    tidx = int(query.data.replace("adm_trmodadd_", ""))
    data = load_trainings()
    trainings = data.get('trainings', [])
    if tidx >= len(trainings):
        await query.answer("Тренинг не найден")
        return

    context.user_data['awaiting_training'] = {'action': 'add_module', 'tidx': tidx, 'step': 'title'}

    await query.message.reply_text(
        f"➕ <b>Новый модуль</b> тренинга «{trainings[tidx].get('title','')}»\n\n"
        f"Шаг 1/2: Напиши <b>заголовок</b> модуля.\nНапример: 3. Скрипты для кассиров\n\n/cancel — отмена",
        parse_mode='HTML'
    )


async def admin_training_module_delete_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Подтверждение удаления модуля."""
    query = update.callback_query
    if not is_admin(query.from_user):
        await query.answer("Нет доступа!")
        return
    await query.answer()

    tidx_str, midx_str = query.data.replace("adm_trmdel_", "").split("_")
    tidx, midx = int(tidx_str), int(midx_str)

    data = load_trainings()
    trainings = data.get('trainings', [])
    if tidx >= len(trainings) or midx >= len(trainings[tidx].get('modules', [])):
        return

    mtitle = trainings[tidx]['modules'][midx].get('title', f'Модуль {midx+1}')
    await query.message.edit_text(
        f"⚠️ <b>Удалить модуль?</b>\n\n«{mtitle}»\n\nЭто действие нельзя отменить!",
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Да, удалить", callback_data=f"adm_trmdelok_{tidx}_{midx}"),
                InlineKeyboardButton("❌ Отмена", callback_data=f"adm_trmod_{tidx}_{midx}"),
            ]
        ])
    )


async def admin_training_module_delete_ok_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Подтверждённое удаление модуля."""
    query = update.callback_query
    if not is_admin(query.from_user):
        await query.answer("Нет доступа!")
        return
    await query.answer()

    tidx_str, midx_str = query.data.replace("adm_trmdelok_", "").split("_")
    tidx, midx = int(tidx_str), int(midx_str)

    data = load_trainings()
    trainings = data.get('trainings', [])
    if tidx < len(trainings) and midx < len(trainings[tidx].get('modules', [])):
        removed = trainings[tidx]['modules'].pop(midx)
        save_trainings(data)
        await query.message.edit_text(
            f"✅ Модуль <b>«{removed.get('title', '')}»</b> удалён.",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 К тренингу", callback_data=f"adm_tr_{tidx}")]
            ])
        )


async def handle_admin_training_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Обработка текстовых шагов для тренингов."""
    state = context.user_data.get('awaiting_training')
    if not state:
        return False

    text = update.message.text.strip() if update.message.text else ""
    if text == '/cancel':
        context.user_data.pop('awaiting_training', None)
        await update.message.reply_text(
            "❌ Отменено.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 К тренингам", callback_data="adm_trainings_mgmt")]])
        )
        return True

    action = state['action']

    if action == 'add_training':
        step = state.get('step')
        if step == 'emoji':
            state['emoji'] = text
            state['step'] = 'title'
            await update.message.reply_text("Шаг 2/3: Напиши <b>название</b> тренинга.\n\n/cancel — отмена", parse_mode='HTML')
            return True
        elif step == 'title':
            state['title'] = text
            state['step'] = 'subtitle'
            await update.message.reply_text(
                "Шаг 3/3: Напиши короткий <b>подзаголовок</b> (одна строка, видна в списке тренингов).\n\n/cancel — отмена",
                parse_mode='HTML'
            )
            return True
        elif step == 'subtitle':
            import uuid
            data = load_trainings()
            trainings = data.setdefault('trainings', [])
            new_training = {
                "id": f"training_{uuid.uuid4().hex[:8]}",
                "emoji": state.get('emoji', '🎓'),
                "title": state.get('title', 'Новый тренинг'),
                "subtitle": text,
                "modules": []
            }
            trainings.append(new_training)
            save_trainings(data)
            tidx = len(trainings) - 1
            context.user_data.pop('awaiting_training', None)
            await update.message.reply_text(
                f"✅ Тренинг <b>«{new_training['title']}»</b> создан! Теперь добавь в него модули.",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("➕ Добавить модуль", callback_data=f"adm_trmodadd_{tidx}")],
                    [InlineKeyboardButton("🔙 К тренингам", callback_data="adm_trainings_mgmt")],
                ])
            )
            return True

    elif action == 'edit_training':
        tidx = state['tidx']
        field = state['field']
        data = load_trainings()
        trainings = data.get('trainings', [])
        if tidx < len(trainings):
            trainings[tidx][field] = text
            save_trainings(data)
            await update.message.reply_text(
                "✅ Поле обновлено!",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 К тренингу", callback_data=f"adm_tr_{tidx}")]])
            )
        context.user_data.pop('awaiting_training', None)
        return True

    elif action == 'edit_module':
        tidx, midx, field = state['tidx'], state['midx'], state['field']
        data = load_trainings()
        trainings = data.get('trainings', [])
        if tidx < len(trainings) and midx < len(trainings[tidx].get('modules', [])):
            trainings[tidx]['modules'][midx][field] = text
            save_trainings(data)
            field_name = "заголовок" if field == 'title' else "содержание"
            await update.message.reply_text(
                f"✅ {field_name.capitalize()} модуля обновлён!",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 К модулю", callback_data=f"adm_trmod_{tidx}_{midx}")]])
            )
        context.user_data.pop('awaiting_training', None)
        return True

    elif action == 'add_module':
        step = state.get('step')
        tidx = state['tidx']
        if step == 'title':
            state['title'] = text
            state['step'] = 'content'
            await update.message.reply_text(
                "Шаг 2/2: Напиши <b>содержание</b> модуля.\n\n"
                "💡 Можно простой HTML: &lt;b&gt;жирный&lt;/b&gt;, &lt;p&gt;абзац&lt;/p&gt;.\n\n/cancel — отмена",
                parse_mode='HTML'
            )
            return True
        elif step == 'content':
            data = load_trainings()
            trainings = data.get('trainings', [])
            if tidx < len(trainings):
                new_module = {"title": state.get('title', 'Новый модуль'), "content": text}
                trainings[tidx].setdefault('modules', []).append(new_module)
                save_trainings(data)
                await update.message.reply_text(
                    f"✅ Модуль <b>«{new_module['title']}»</b> добавлен!",
                    parse_mode='HTML',
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 К тренингу", callback_data=f"adm_tr_{tidx}")]])
                )
            context.user_data.pop('awaiting_training', None)
            return True

    return False


# ─── Управление событиями ──────────────────────────────────────────

EVENT_TYPES = {
    'cleaning':  ('🧹', 'Генеральная уборка'),
    'training':  ('🎓', 'Тренинг'),
    'meeting':   ('👥', 'Собрание'),
    'important': ('❗', 'Важное событие'),
    'other':     ('📌', 'Другое'),
}

BRANCHES = [
    ('tsum', 'ТСМ'),
    ('shevchenko', 'Шевченко'),
    ('forum', 'Форум'),
    ('itpark', 'Айти Парк'),
    ('foodmall', 'Фудмолл'),
]
BRANCH_NAMES = dict(BRANCHES)


def format_event_branches(ev):
    branches = ev.get('branches') or ['all']
    if 'all' in branches:
        return "🌍 Все филиалы"
    names = [BRANCH_NAMES[b] for b in branches if b in BRANCH_NAMES]
    return "🏢 " + ", ".join(names) if names else "—"


def render_branch_picker(selected):
    """selected: 'all' или set() строковых id филиалов."""
    is_all = selected == 'all'
    if is_all:
        summary = "✅ Все филиалы"
    elif selected:
        summary = "Выбрано: " + ", ".join(BRANCH_NAMES[b] for b in sorted(selected))
    else:
        summary = "Ничего не выбрано — отметь хотя бы один филиал"

    text = f"🏢 <b>Филиал(ы) события</b>\n\n{summary}"

    buttons = []
    row = []
    for bid, name in BRANCHES:
        checked = is_all or (not is_all and bid in selected)
        row.append(InlineKeyboardButton(f"{'✅ ' if checked else ''}{name}", callback_data=f"adm_evbr_t_{bid}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton(f"{'✅ ' if is_all else ''}🌍 Все филиалы", callback_data="adm_evbr_all")])
    buttons.append([InlineKeyboardButton("✔️ Готово", callback_data="adm_evbr_done")])
    return text, InlineKeyboardMarkup(buttons)


def event_sort_key(ev):
    return (ev.get('date', '9999-99-99'), ev.get('time') or '00:00')


def format_event_when(ev):
    d = ev.get('date', '')
    parts = d.split('-')
    disp_date = f"{parts[2]}.{parts[1]}.{parts[0]}" if len(parts) == 3 else d
    if ev.get('repeat') == 'weekly':
        from events_util import every_label
        when = f"🔁 {every_label(ev)}"
        when += f" {ev['time']}" if ev.get('time') else ""
        return f"{when} (с {disp_date})"
    return f"{disp_date} {ev['time']}" if ev.get('time') else disp_date


def parse_event_date_input(text):
    """Парсит 'ДД.ММ.ГГГГ' или 'ДД.ММ.ГГГГ ЧЧ:ММ' -> (date_iso, time) или None."""
    m = re.fullmatch(r'(\d{1,2})\.(\d{1,2})\.(\d{4})(?:\s+(\d{1,2}):(\d{2}))?', text.strip())
    if not m:
        return None
    day, month, year, hh, mm = m.groups()
    day, month, year = int(day), int(month), int(year)
    if not (1 <= day <= 31 and 1 <= month <= 12):
        return None
    time_str = ''
    if hh is not None:
        hh, mm = int(hh), int(mm)
        if not (0 <= hh <= 23 and 0 <= mm <= 59):
            return None
        time_str = f"{hh:02d}:{mm:02d}"
    return f"{year:04d}-{month:02d}-{day:02d}", time_str


def event_type_buttons(callback_prefix, suffix=""):
    row1, row2 = [], []
    items = list(EVENT_TYPES.items())
    for i, (key, (emoji, label)) in enumerate(items):
        btn = InlineKeyboardButton(f"{emoji} {label}", callback_data=f"{callback_prefix}{key}{suffix}")
        (row1 if i < 3 else row2).append(btn)
    return [row1, row2] if row2 else [row1]


async def admin_events_mgmt_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Список событий, отсортированный по дате."""
    query = update.callback_query
    if not is_admin(query.from_user):
        await query.answer("Нет доступа!")
        return
    await query.answer()

    data = load_events()
    events = data.get('events', [])
    order = sorted(range(len(events)), key=lambda i: event_sort_key(events[i]))

    text = "📅 <b>Управление событиями</b>\n\n"
    text += f"Событий: <b>{len(events)}</b>\n\n"
    text += "Сотрудники видят этот список в приложении (раздел «События»)."

    buttons = []
    for idx in order:
        ev = events[idx]
        emoji = ev.get('emoji', '📌')
        label = f"{emoji} {format_event_when(ev)} — {ev.get('title', '')}"
        if len(label) > 60:
            label = label[:57] + '…'
        buttons.append([InlineKeyboardButton(label, callback_data=f"adm_ev_{idx}")])

    buttons.append([InlineKeyboardButton("➕ Добавить событие", callback_data="adm_evadd")])
    buttons.append([InlineKeyboardButton("🔙 Назад", callback_data="adm_menu")])

    await query.message.edit_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(buttons))


async def admin_event_add_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начать добавление события — выбор типа."""
    query = update.callback_query
    if not is_admin(query.from_user):
        await query.answer("Нет доступа!")
        return
    await query.answer()

    await query.message.reply_text(
        "➕ <b>Новое событие</b>\n\nШаг 1/5: выбери тип события:",
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(event_type_buttons("adm_evtype_"))
    )


async def admin_event_type_pick_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Тип выбран при добавлении — просим название."""
    query = update.callback_query
    if not is_admin(query.from_user):
        await query.answer("Нет доступа!")
        return
    await query.answer()

    ev_type = query.data.replace("adm_evtype_", "")
    if ev_type not in EVENT_TYPES:
        return
    emoji, label = EVENT_TYPES[ev_type]

    context.user_data['awaiting_event'] = {'action': 'add', 'type': ev_type, 'step': 'title'}

    await query.message.edit_text(
        f"➕ <b>Новое событие</b> — {emoji} {label}\n\n"
        f"Шаг 2/5: напиши <b>название</b> события.\nНапример: Генеральная уборка кухни\n\n/cancel — отмена",
        parse_mode='HTML'
    )


def render_event_view(idx, ev):
    emoji, label = EVENT_TYPES.get(ev.get('type'), ('📌', 'Другое'))
    text = (
        f"{ev.get('emoji', emoji)} <b>{ev.get('title', '')}</b>\n"
        f"<i>{label}</i>\n\n"
        f"🗓 <b>Когда:</b> {format_event_when(ev)}\n"
        f"🏢 <b>Филиал:</b> {format_event_branches(ev)}\n\n"
        f"{ev.get('description', '') or '<i>Без описания</i>'}"
    )
    weekly = ev.get('repeat') == 'weekly'
    if weekly and ev.get('recap'):
        text += ("\n\n📚 <i>Название каждого занятия подставляется автоматически из тренинга, "
                 "который прошёл в воскресенье перед ним (событие типа «Тренинг»).</i>")
    repeat_row = [InlineKeyboardButton(
        f"🔁 Каждую неделю: {'вкл' if weekly else 'выкл'}", callback_data=f"adm_evrep_{idx}")]
    if weekly:
        repeat_row.append(InlineKeyboardButton(
            f"📚 Тема из вс: {'вкл' if ev.get('recap') else 'выкл'}", callback_data=f"adm_evrecap_{idx}"))
    buttons = InlineKeyboardMarkup([
        repeat_row,
        [
            InlineKeyboardButton("✏️ Название", callback_data=f"adm_evedit_title_{idx}"),
            InlineKeyboardButton("✏️ Дата/время", callback_data=f"adm_evedit_date_{idx}"),
        ],
        [
            InlineKeyboardButton("✏️ Описание", callback_data=f"adm_evedit_description_{idx}"),
            InlineKeyboardButton("✏️ Тип", callback_data=f"adm_evedit_type_{idx}"),
        ],
        [InlineKeyboardButton("✏️ Филиал", callback_data=f"adm_evedit_branches_{idx}")],
        [InlineKeyboardButton("🗑️ Удалить событие", callback_data=f"adm_evdel_{idx}")],
        [InlineKeyboardButton("🔙 К событиям", callback_data="adm_events_mgmt")],
    ])
    return text, buttons


async def admin_event_view_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Карточка события."""
    query = update.callback_query
    if not is_admin(query.from_user):
        await query.answer("Нет доступа!")
        return
    await query.answer()

    idx = int(query.data.replace("adm_ev_", ""))
    data = load_events()
    events = data.get('events', [])
    if idx >= len(events):
        await query.answer("Событие не найдено")
        return

    text, buttons = render_event_view(idx, events[idx])
    await query.message.edit_text(text, parse_mode='HTML', reply_markup=buttons)


async def admin_event_edit_field_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начать редактирование поля события."""
    query = update.callback_query
    if not is_admin(query.from_user):
        await query.answer("Нет доступа!")
        return
    await query.answer()

    parts = query.data.replace("adm_evedit_", "").rsplit("_", 1)
    field, idx = parts[0], int(parts[1])

    if field == 'type':
        await query.message.edit_text(
            "✏️ Выбери новый тип события:",
            reply_markup=InlineKeyboardMarkup(event_type_buttons("adm_evsettype_", f"_{idx}"))
        )
        return

    if field == 'branches':
        data = load_events()
        events = data.get('events', [])
        if idx >= len(events):
            return
        existing = events[idx].get('branches') or ['all']
        selected = 'all' if 'all' in existing else set(existing)
        context.user_data['awaiting_event'] = {'action': 'edit_branches', 'idx': idx, 'selected': selected}
        text, kb = render_branch_picker(selected)
        await query.message.edit_text(text, parse_mode='HTML', reply_markup=kb)
        return

    context.user_data['awaiting_event'] = {'action': 'edit', 'field': field, 'idx': idx}

    prompts = {
        'title': "✉️ Пришли новое <b>название</b> события.",
        'date': "✉️ Пришли новую <b>дату</b> в формате ДД.ММ.ГГГГ, например 05.10.2026, "
                "или с временем: 05.10.2026 10:00.",
        'description': "✉️ Пришли новое <b>описание</b> события (или «-», чтобы убрать описание).",
    }
    await query.message.reply_text(prompts.get(field, "✉️ Пришли новое значение.") + "\n\n/cancel — отмена", parse_mode='HTML')


async def admin_event_set_type_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Прямая смена типа события (без текстового ввода)."""
    query = update.callback_query
    if not is_admin(query.from_user):
        await query.answer("Нет доступа!")
        return
    await query.answer()

    rest = query.data.replace("adm_evsettype_", "")
    ev_type, idx_str = rest.rsplit("_", 1)
    idx = int(idx_str)
    if ev_type not in EVENT_TYPES:
        return

    data = load_events()
    events = data.get('events', [])
    if idx >= len(events):
        return
    emoji, _ = EVENT_TYPES[ev_type]
    events[idx]['type'] = ev_type
    events[idx]['emoji'] = emoji
    save_events(data)

    text, buttons = render_event_view(idx, events[idx])
    await query.message.edit_text(text, parse_mode='HTML', reply_markup=buttons)


async def admin_event_toggle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Переключить еженедельный повтор (adm_evrep_) или подстановку темы из воскресного тренинга (adm_evrecap_)."""
    query = update.callback_query
    if not is_admin(query.from_user):
        await query.answer("Нет доступа!")
        return
    await query.answer()

    is_recap = query.data.startswith("adm_evrecap_")
    idx = int(query.data.rsplit("_", 1)[1])
    data = load_events()
    events = data.get('events', [])
    if idx >= len(events):
        return
    ev = events[idx]
    if is_recap:
        ev['recap'] = not ev.get('recap')
    elif ev.get('repeat') == 'weekly':
        ev.pop('repeat', None)
        ev.pop('recap', None)
    else:
        ev['repeat'] = 'weekly'
    save_events(data)

    text, buttons = render_event_view(idx, ev)
    await query.message.edit_text(text, parse_mode='HTML', reply_markup=buttons)


async def admin_event_delete_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Подтверждение удаления события."""
    query = update.callback_query
    if not is_admin(query.from_user):
        await query.answer("Нет доступа!")
        return
    await query.answer()

    idx = int(query.data.replace("adm_evdel_", ""))
    data = load_events()
    events = data.get('events', [])
    if idx >= len(events):
        return

    title = events[idx].get('title', f'Событие {idx+1}')
    await query.message.edit_text(
        f"⚠️ <b>Удалить событие?</b>\n\n«{title}»\n\nЭто действие нельзя отменить!",
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Да, удалить", callback_data=f"adm_evdelok_{idx}"),
                InlineKeyboardButton("❌ Отмена", callback_data=f"adm_ev_{idx}"),
            ]
        ])
    )


async def admin_event_delete_ok_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Подтверждённое удаление события."""
    query = update.callback_query
    if not is_admin(query.from_user):
        await query.answer("Нет доступа!")
        return
    await query.answer()

    idx = int(query.data.replace("adm_evdelok_", ""))
    data = load_events()
    events = data.get('events', [])
    if idx < len(events):
        removed = events.pop(idx)
        save_events(data)
        await query.message.edit_text(
            f"✅ Событие <b>«{removed.get('title', '')}»</b> удалено.",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 К событиям", callback_data="adm_events_mgmt")]
            ])
        )


async def handle_admin_event_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Текстовые шаги добавления/редактирования события."""
    state = context.user_data.get('awaiting_event')
    if not state:
        return False

    text = update.message.text.strip() if update.message.text else ""
    if text == '/cancel':
        context.user_data.pop('awaiting_event', None)
        await update.message.reply_text(
            "❌ Отменено.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 К событиям", callback_data="adm_events_mgmt")]])
        )
        return True

    action = state['action']

    if action == 'add':
        step = state.get('step')
        if step == 'title':
            state['title'] = text
            state['step'] = 'date'
            await update.message.reply_text(
                "Шаг 3/3: пришли <b>дату</b> события в формате ДД.ММ.ГГГГ (например 05.10.2026), "
                "или с временем: 05.10.2026 10:00.\n\n/cancel — отмена",
                parse_mode='HTML'
            )
            return True
        elif step == 'date':
            parsed = parse_event_date_input(text)
            if not parsed:
                await update.message.reply_text(
                    "❌ Не похоже на дату. Формат: ДД.ММ.ГГГГ или ДД.ММ.ГГГГ ЧЧ:ММ.\nПопробуй ещё раз или /cancel."
                )
                return True
            date_iso, time_str = parsed
            state['date'] = date_iso
            state['time'] = time_str
            state['step'] = 'description'
            await update.message.reply_text(
                "Шаг 4/5: добавь короткое <b>описание</b> (необязательно — отправь «-», чтобы пропустить).\n\n/cancel — отмена",
                parse_mode='HTML'
            )
            return True
        elif step == 'description':
            state['description'] = '' if text == '-' else text
            state['step'] = 'branches'
            state['selected'] = 'all'
            text_msg, kb = render_branch_picker('all')
            await update.message.reply_text(
                "Шаг 5/5: " + text_msg, parse_mode='HTML', reply_markup=kb
            )
            return True

    elif action == 'edit':
        idx, field = state['idx'], state['field']
        data = load_events()
        events = data.get('events', [])
        if idx >= len(events):
            context.user_data.pop('awaiting_event', None)
            return True

        if field == 'date':
            parsed = parse_event_date_input(text)
            if not parsed:
                await update.message.reply_text(
                    "❌ Не похоже на дату. Формат: ДД.ММ.ГГГГ или ДД.ММ.ГГГГ ЧЧ:ММ.\nПопробуй ещё раз или /cancel."
                )
                return True
            events[idx]['date'], events[idx]['time'] = parsed
        elif field == 'description':
            events[idx]['description'] = '' if text == '-' else text
        else:
            events[idx][field] = text

        save_events(data)
        context.user_data.pop('awaiting_event', None)
        await update.message.reply_text(
            "✅ Событие обновлено!",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 К событию", callback_data=f"adm_ev_{idx}")]])
        )
        return True

    return False


async def admin_event_branch_toggle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Переключить один филиал в селекторе."""
    query = update.callback_query
    if not is_admin(query.from_user):
        await query.answer("Нет доступа!")
        return

    state = context.user_data.get('awaiting_event')
    if not state:
        await query.answer()
        return

    bid = query.data.replace("adm_evbr_t_", "")
    sel = state.get('selected', 'all')
    if sel == 'all':
        sel = {bid}
    else:
        sel = set(sel)
        if bid in sel:
            sel.discard(bid)
        else:
            sel.add(bid)
    state['selected'] = sel

    await query.answer()
    text, kb = render_branch_picker(sel)
    await query.message.edit_text(text, parse_mode='HTML', reply_markup=kb)


async def admin_event_branch_all_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выбрать «Все филиалы»."""
    query = update.callback_query
    if not is_admin(query.from_user):
        await query.answer("Нет доступа!")
        return

    state = context.user_data.get('awaiting_event')
    if not state:
        await query.answer()
        return

    state['selected'] = 'all'
    await query.answer()
    text, kb = render_branch_picker('all')
    await query.message.edit_text(text, parse_mode='HTML', reply_markup=kb)


async def admin_event_branch_done_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Подтвердить выбор филиалов — сохранить событие (add) или обновить (edit_branches)."""
    query = update.callback_query
    if not is_admin(query.from_user):
        await query.answer("Нет доступа!")
        return

    state = context.user_data.get('awaiting_event')
    if not state:
        await query.answer()
        return

    sel = state.get('selected', 'all')
    if sel != 'all' and len(sel) == 0:
        await query.answer("Выбери хотя бы один филиал или «Все филиалы»", show_alert=True)
        return
    branches = ['all'] if sel == 'all' else sorted(sel)
    await query.answer()

    if state['action'] == 'add':
        import uuid
        emoji, _ = EVENT_TYPES.get(state['type'], ('📌', 'Другое'))
        data = load_events()
        events = data.setdefault('events', [])
        new_event = {
            "id": f"evt_{uuid.uuid4().hex[:8]}",
            "type": state['type'],
            "emoji": emoji,
            "title": state.get('title', 'Событие'),
            "date": state['date'],
            "time": state.get('time', ''),
            "description": state.get('description', ''),
            "branches": branches,
        }
        events.append(new_event)
        save_events(data)
        context.user_data.pop('awaiting_event', None)
        await query.message.edit_text(
            f"✅ Событие <b>«{new_event['title']}»</b> добавлено на {format_event_when(new_event)}!\n"
            f"🏢 {format_event_branches(new_event)}",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 К событиям", callback_data="adm_events_mgmt")]])
        )
    elif state['action'] == 'edit_branches':
        idx = state['idx']
        data = load_events()
        events = data.get('events', [])
        context.user_data.pop('awaiting_event', None)
        if idx >= len(events):
            return
        events[idx]['branches'] = branches
        save_events(data)
        text, kb = render_event_view(idx, events[idx])
        await query.message.edit_text(text, parse_mode='HTML', reply_markup=kb)


def get_handlers():
    return [
        CommandHandler("admin", admin_command),
        CommandHandler("cancel", cancel_command),
        CallbackQueryHandler(admin_settings_callback, pattern="^adm_settings$"),
        CallbackQueryHandler(admin_set_setting_callback, pattern="^adm_set_"),
        CallbackQueryHandler(admin_test_fact_callback, pattern="^adm_test_fact$"),
        CallbackQueryHandler(admin_test_events_callback, pattern="^adm_test_events$"),
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
        # ── Управление тренингами ──
        CallbackQueryHandler(admin_trainings_mgmt_callback, pattern="^adm_trainings_mgmt$"),
        CallbackQueryHandler(admin_training_add_callback, pattern="^adm_tradd$"),
        CallbackQueryHandler(admin_training_edit_callback, pattern="^adm_tredit_"),
        CallbackQueryHandler(admin_training_delete_ok_callback, pattern="^adm_trdelok_"),
        CallbackQueryHandler(admin_training_delete_callback, pattern="^adm_trdel_"),
        CallbackQueryHandler(admin_training_module_add_callback, pattern="^adm_trmodadd_"),
        CallbackQueryHandler(admin_training_module_edit_callback, pattern="^adm_trmedit_"),
        CallbackQueryHandler(admin_training_module_delete_ok_callback, pattern="^adm_trmdelok_"),
        CallbackQueryHandler(admin_training_module_delete_callback, pattern="^adm_trmdel_"),
        CallbackQueryHandler(admin_training_module_callback, pattern="^adm_trmod_"),
        CallbackQueryHandler(admin_training_callback, pattern="^adm_tr_"),
        # ── Управление событиями ──
        CallbackQueryHandler(admin_events_mgmt_callback, pattern="^adm_events_mgmt$"),
        CallbackQueryHandler(admin_event_add_callback, pattern="^adm_evadd$"),
        CallbackQueryHandler(admin_event_type_pick_callback, pattern="^adm_evtype_"),
        CallbackQueryHandler(admin_event_set_type_callback, pattern="^adm_evsettype_"),
        CallbackQueryHandler(admin_event_edit_field_callback, pattern="^adm_evedit_"),
        CallbackQueryHandler(admin_event_delete_ok_callback, pattern="^adm_evdelok_"),
        CallbackQueryHandler(admin_event_delete_callback, pattern="^adm_evdel_"),
        CallbackQueryHandler(admin_event_branch_toggle_callback, pattern="^adm_evbr_t_"),
        CallbackQueryHandler(admin_event_branch_all_callback, pattern="^adm_evbr_all$"),
        CallbackQueryHandler(admin_event_branch_done_callback, pattern="^adm_evbr_done$"),
        CallbackQueryHandler(admin_event_toggle_callback, pattern="^adm_evre(p|cap)_"),
        CallbackQueryHandler(admin_event_view_callback, pattern="^adm_ev_"),
        # ── Управление администраторами ──
        CallbackQueryHandler(admin_admins_callback, pattern="^adm_admins$"),
        CallbackQueryHandler(admin_add_admin_callback, pattern="^adm_addadm$"),
        CallbackQueryHandler(admin_pick_user_callback, pattern="^adm_pickusr_"),
        CallbackQueryHandler(admin_set_role_callback, pattern="^adm_setrole_"),
        CallbackQueryHandler(admin_confirm_remove_admin_callback, pattern="^adm_rmadm_ok_"),
        CallbackQueryHandler(admin_remove_admin_callback, pattern="^adm_rmadm_"),
        # Текстовые ответы и фото и аудио (должен быть последним!)
        MessageHandler((filters.TEXT | filters.PHOTO | filters.VOICE | filters.AUDIO) & ~filters.COMMAND, handle_admin_text),
    ]

