"""Обработчик /start и главного меню."""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler
import database as db
from config import WEBAPP_URL


def get_main_menu_keyboard():
    """Клавиатура с кнопкой запуска Web App и админкой."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(
            text="📱 Открыть приложение", 
            web_app=WebAppInfo(url=f"{WEBAPP_URL}?v=3")
        )]
    ])


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /start."""
    user = update.effective_user
    db.get_or_create_user(user.id, user.username, user.first_name)

    text = (
        f"🍵 <b>Добро пожаловать в Matcha Club!</b>\n\n"
        f"Привет, <b>{user.first_name}</b>! 👋\n\n"
        f"Я — бот Matcha Club & Mari Wellness.\n"
        f"Здесь ты найдёшь:\n\n"
        f"📖 <b>Велкам-бук</b> — всё о компании\n"
        f"📋 <b>Меню</b> — блюда и напитки с КБЖУ\n"
        f"🎯 <b>Квиз</b> — проверь знания и заработай баллы\n"
        f"💡 <b>Факты</b> — интересное о здоровом питании\n"
        f"👤 <b>Профиль</b> — баллы и награды\n\n"
        f"Выбери раздел 👇"
    )

    from telegram import ReplyKeyboardRemove
    
    # Убираем старую клавиатуру с кнопкой локации
    await update.message.reply_text(
        "👋 Добро пожаловать!",
        reply_markup=ReplyKeyboardRemove()
    )

    await update.message.reply_text(
        text,
        parse_mode='HTML',
        reply_markup=get_main_menu_keyboard()
    )


async def main_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Возврат в главное меню."""
    query = update.callback_query
    await query.answer()

    user = update.effective_user
    text = (
        f"🍵 <b>Matcha Club</b>\n\n"
        f"Привет, <b>{user.first_name}</b>!\n"
        f"Выбери раздел 👇"
    )

    # Если сообщение — фото, удаляем и отправляем текстовое
    if query.message.photo:
        try:
            await query.message.delete()
        except Exception:
            pass
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=text,
            parse_mode='HTML',
            reply_markup=get_main_menu_keyboard()
        )
    else:
        await query.message.edit_text(
            text,
            parse_mode='HTML',
            reply_markup=get_main_menu_keyboard()
        )


async def myid_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /myid — показать Telegram ID."""
    user = update.effective_user
    await update.message.reply_text(
        f"🆔 <b>Твой Telegram ID:</b> <code>{user.id}</code>\n"
        f"👤 Username: @{user.username or '—'}\n\n"
        f"Этот ID используется для настройки админ-панели.",
        parse_mode='HTML'
    )


def get_handlers():
    """Вернуть список хэндлеров."""
    return [
        CommandHandler("start", start_command),
        CommandHandler("myid", myid_command),
        CallbackQueryHandler(main_menu_callback, pattern="^main_menu$"),
    ]
