"""Обработчик отметки на смене (перенаправление в Mini App)."""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler

async def staff_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отправляет кнопку для открытия Mini App."""
    from config import WEBAPP_URL
    if not WEBAPP_URL:
        await update.message.reply_text("Mini App URL не настроен.")
        return

    keyboard = [
        [InlineKeyboardButton("📱 Открыть приложение", web_app={"url": WEBAPP_URL})]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "👋 <b>Меню сотрудника</b>\n\n"
        "Отметка на смене теперь доступна прямо в нашем приложении! "
        "Откройте его и нажмите на карточку <b>«Смена»</b> на главной странице.",
        reply_markup=reply_markup,
        parse_mode='HTML'
    )

def get_handlers():
    """Вернуть список хэндлеров."""
    return [
        CommandHandler("staff", staff_command)
    ]
