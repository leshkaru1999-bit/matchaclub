"""Обработчик фактов о здоровом питании."""
import json
import os
import random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CallbackQueryHandler
from config import DATA_DIR


def load_facts():
    """Загрузить факты."""
    path = os.path.join(DATA_DIR, 'facts.json')
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


CATEGORY_NAMES = {
    "matcha": "🍵 Матча",
    "superfoods": "🥑 Суперфуды",
    "nutrition": "🥗 Питание",
    "wellness": "🧘 Велнес",
    "myths": "🔍 Мифы",
}


async def random_fact_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать случайный факт."""
    query = update.callback_query
    await query.answer()

    data = load_facts()
    fact = random.choice(data['facts'])

    cat_name = CATEGORY_NAMES.get(fact['category'], fact['category'])

    text = (
        f"{fact['emoji']} <b>Факт дня</b>\n"
        f"<i>{cat_name}</i>\n\n"
        f"{fact['text']}"
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Ещё факт", callback_data="random_fact")],
        [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")],
    ])

    await query.message.edit_text(text, parse_mode='HTML', reply_markup=keyboard)


def get_handlers():
    """Вернуть список хэндлеров."""
    return [
        CallbackQueryHandler(random_fact_callback, pattern="^random_fact$"),
    ]
