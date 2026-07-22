"""Обработчик меню с навигацией по категориям и поддержкой фото."""
import json
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import ContextTypes, CallbackQueryHandler
from config import DATA_DIR, PHOTOS_DIR


_menu_cache = None

# Маппинг блюд к фото файлам
PHOTO_MAP = {
    "Мини-киш с лососем и сыром": "mini_kish_salmon.jpg",
    "Киш с овощами и сыром": "kish_vegetables.jpg",
    "Вафля с яйцом пашот": "waffle_poached_egg.jpg",
    "Вафля сладкая": "waffle_sweet.jpg",
    "Каша из цельного овса с ягодами": "oatmeal_berries.jpg",
    "Протеиновые сырники с ягодами": "syrniki_berries.jpg",
    "Белковый омлет с креветками": "omelet_shrimp.jpg",
    "Скрембл с лососем и овощными оладьями": "scramble_salmon.jpg",
    "Чечевичный крем-суп с бараниной": "soup_lentil.jpg",
    "Крем-суп минестроне": "soup_minestrone.jpg",
    "Классический омлет с сыром": "omelet_classic.jpg",
    "Авокадо-тост с яйцом пашот и халуми": "avocado_toast.jpg",
    "Шакшука": "shakshuka.jpg",
    "Йогурт-боул с гранолой": "yogurt_bowl.jpg",
    "Вафля с грибами": "waffle_mushrooms.jpg",
    "Поке-боул с курицей": "poke_chicken.jpg",
    "Боул с курицей и киноа": "poke_chicken.jpg",
    "Поке-боул с лососем": "poke_salmon.jpg",
    "Боул с лососем слабой соли": "poke_salmon.jpg",
    "Фреш-ролл с курицей": "fresh_roll_chicken.jpg",
    "Фреш-ролл с ростбифом": "fresh_roll_beef.jpg",
    "Поке-боул с говядиной": "poke_beef.jpg",
}


def load_menu():
    """Загрузить данные меню (с кешированием)."""
    global _menu_cache
    if _menu_cache is None:
        path = os.path.join(DATA_DIR, 'menu.json')
        with open(path, 'r', encoding='utf-8') as f:
            _menu_cache = json.load(f)
    return _menu_cache


def reload_menu():
    """Перезагрузить кеш меню."""
    global _menu_cache
    _menu_cache = None
    return load_menu()


def get_photo_path(item: dict):
    """Получить путь к фото блюда, если оно есть."""
    filename = item.get('photo') or PHOTO_MAP.get(item.get('name'))
    if filename:
        path = os.path.join(PHOTOS_DIR, filename)
        if os.path.exists(path):
            return path
    return None


async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать типы меню: Кухня / Бар."""
    query = update.callback_query
    await query.answer()

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🍽️ Кухня", callback_data="mt_kitchen"),
            InlineKeyboardButton("🍹 Бар", callback_data="mt_bar"),
        ],
        [InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")],
    ])

    await query.message.edit_text(
        "📋 <b>Меню Matcha Club</b>\n\n"
        "Выбери раздел 👇",
        parse_mode='HTML',
        reply_markup=keyboard
    )


async def menu_type_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать категории выбранного типа."""
    query = update.callback_query
    await query.answer()

    menu_type = query.data.replace("mt_", "")  # kitchen or bar
    data = load_menu()

    type_name = "🍽️ Кухня" if menu_type == "kitchen" else "🍹 Бар"
    categories = [c for c in data['categories'] if c['type'] == menu_type]

    buttons = []
    row = []
    for cat in categories:
        row.append(InlineKeyboardButton(cat['name'], callback_data=f"mc_{cat['id']}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton("🔙 Меню", callback_data="menu")])

    await query.message.edit_text(
        f"📋 <b>{type_name}</b>\n\nВыбери категорию 👇",
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(buttons)
    )


async def menu_category_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать блюда/напитки в категории."""
    query = update.callback_query
    await query.answer()

    cat_id = query.data.replace("mc_", "")
    data = load_menu()

    category = None
    for c in data['categories']:
        if c['id'] == cat_id:
            category = c
            break

    if not category:
        await query.message.edit_text("❌ Категория не найдена.")
        return

    buttons = []
    for i, item in enumerate(category['items']):
        # Добавляем 📷 если есть фото
        photo_indicator = " 📷" if get_photo_path(item) else ""
        buttons.append([InlineKeyboardButton(
            f"{item['name']}{photo_indicator}",
            callback_data=f"mi_{cat_id}_{i}"
        )])

    back_type = "mt_" + category['type']
    buttons.append([InlineKeyboardButton("🔙 Назад", callback_data=back_type)])

    await query.message.edit_text(
        f"{category['name']}\n\n"
        f"Всего позиций: <b>{len(category['items'])}</b>\n"
        f"📷 — есть фото\n"
        f"Выбери блюдо для подробностей 👇",
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(buttons)
    )


async def menu_item_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать детали блюда/напитка с фото."""
    query = update.callback_query
    await query.answer()

    parts = query.data.replace("mi_", "").rsplit("_", 1)
    cat_id = parts[0]
    item_idx = int(parts[1])

    data = load_menu()
    category = None
    for c in data['categories']:
        if c['id'] == cat_id:
            category = c
            break

    if not category or item_idx >= len(category['items']):
        await query.message.edit_text("❌ Блюдо не найдено.")
        return

    item = category['items'][item_idx]

    # Формируем карточку
    text = f"<b>{item['name']}</b>\n\n"
    if item.get('description'):
        text += f"📝 {item['description']}\n\n"

    # КБЖУ
    if item.get('calories') and item['calories'] > 0:
        text += (
            f"📊 <b>КБЖУ (на 100г):</b>\n"
            f"🔸 Калории: {item['calories']} ккал\n"
            f"🔸 Белки: {item['protein']}г\n"
            f"🔸 Жиры: {item['fat']}г\n"
            f"🔸 Углеводы: {item['carbs']}г\n"
        )

    if item.get('volume'):
        text += f"\n📏 Объём: {item['volume']}"

    # Навигация: предыдущий/следующий
    nav_buttons = []
    if item_idx > 0:
        nav_buttons.append(InlineKeyboardButton("⬅️", callback_data=f"mi_{cat_id}_{item_idx - 1}"))
    nav_buttons.append(InlineKeyboardButton(f"{item_idx + 1}/{len(category['items'])}", callback_data="noop"))
    if item_idx < len(category['items']) - 1:
        nav_buttons.append(InlineKeyboardButton("➡️", callback_data=f"mi_{cat_id}_{item_idx + 1}"))

    keyboard = InlineKeyboardMarkup([
        nav_buttons,
        [InlineKeyboardButton("🔙 Назад к категории", callback_data=f"mc_{cat_id}")],
        [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")],
    ])

    # Проверяем, есть ли фото
    photo_path = get_photo_path(item)

    if photo_path:
        # Удаляем старое сообщение и отправляем фото с текстом
        try:
            await query.message.delete()
        except Exception:
            pass
        with open(photo_path, 'rb') as photo_file:
            await context.bot.send_photo(
                chat_id=query.message.chat_id,
                photo=photo_file,
                caption=text,
                parse_mode='HTML',
                reply_markup=keyboard
            )
    else:
        # Если текущее сообщение — фото, удаляем и отправляем текст
        if query.message.photo:
            try:
                await query.message.delete()
            except Exception:
                pass
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=text,
                parse_mode='HTML',
                reply_markup=keyboard
            )
        else:
            await query.message.edit_text(text, parse_mode='HTML', reply_markup=keyboard)


async def noop_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Пустой callback для кнопки-счётчика."""
    await update.callback_query.answer()


def get_handlers():
    """Вернуть список хэндлеров."""
    return [
        CallbackQueryHandler(menu_callback, pattern="^menu$"),
        CallbackQueryHandler(menu_type_callback, pattern="^mt_"),
        CallbackQueryHandler(menu_category_callback, pattern="^mc_"),
        CallbackQueryHandler(menu_item_callback, pattern="^mi_"),
        CallbackQueryHandler(noop_callback, pattern="^noop$"),
    ]
