"""Обработчик велкам-бука."""
import json
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CallbackQueryHandler
from config import DATA_DIR


def load_welcome_data():
    """Загрузить данные велкам-бука."""
    path = os.path.join(DATA_DIR, 'welcome.json')
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


async def welcome_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать разделы велкам-бука."""
    query = update.callback_query
    await query.answer()

    data = load_welcome_data()
    buttons = []
    row = []
    for i, section in enumerate(data['sections']):
        row.append(InlineKeyboardButton(section['title'], callback_data=f"wb_{section['id']}"))
        if len(row) == 2 or i == len(data['sections']) - 1:
            buttons.append(row)
            row = []
    buttons.append([InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")])

    text = (
        f"📖 <b>Велкам-бук</b>\n"
        f"<b>{data['company_name']}</b>\n\n"
        f"{data['welcome_message']}\n\n"
        f"Выбери раздел 👇"
    )

    await query.message.edit_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(buttons))


async def welcome_section_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать конкретный раздел велкам-бука."""
    query = update.callback_query
    await query.answer()

    section_id = query.data.replace("wb_", "")
    data = load_welcome_data()

    section = None
    for s in data['sections']:
        if s['id'] == section_id:
            section = s
            break

    if not section:
        await query.message.edit_text("❌ Раздел не найден.")
        return

    # Обрезаем текст если слишком длинный для Telegram (4096 символов)
    content = section['content']
    if len(content) > 3800:
        content = content[:3800] + "\n\n<i>...продолжение в следующем обновлении</i>"

    text = f"{section['title']}\n\n{content}"

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Велкам-бук", callback_data="welcome")],
        [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")],
    ])

    await query.message.edit_text(text, parse_mode='HTML', reply_markup=keyboard)


def get_handlers():
    """Вернуть список хэндлеров."""
    return [
        CallbackQueryHandler(welcome_callback, pattern="^welcome$"),
        CallbackQueryHandler(welcome_section_callback, pattern="^wb_"),
    ]
