"""Обработчик профиля, баллов и наград."""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CallbackQueryHandler
import database as db
from config import get_settings


async def profile_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать профиль пользователя."""
    query = update.callback_query
    await query.answer()

    user = update.effective_user
    stats = db.get_user_stats(user.id)
    if not stats:
        db.get_or_create_user(user.id, user.username, user.first_name)
        stats = db.get_user_stats(user.id)

    # Ранг по баллам
    points = stats['points']
    if points >= 100:
        rank = "🏆 Мастер матчи"
    elif points >= 50:
        rank = "⭐ Эксперт"
    elif points >= 20:
        rank = "🌿 Знаток"
    elif points >= 5:
        rank = "🌱 Новичок"
    else:
        rank = "🫖 Стажёр"

    # Прогресс до следующего напитка
    cost = get_settings().get('points_for_drink', 100)
    drinks_available = points // cost
    progress_to_next = points % cost
    progress_bar_filled = int((progress_to_next / cost) * 10)
    progress_bar = "▓" * progress_bar_filled + "░" * (10 - progress_bar_filled)

    text = (
        f"👤 <b>Профиль</b>\n\n"
        f"👋 {user.first_name}\n"
        f"📛 Ранг: {rank}\n\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"💎 <b>Баллы: {points}</b>\n"
        f"🍹 Напитков доступно: <b>{drinks_available}</b>\n"
        f"📊 До след. напитка: [{progress_bar}] {progress_to_next}/{cost}\n"
        f"━━━━━━━━━━━━━━━━\n\n"
        f"📝 <b>Статистика:</b>\n"
        f"🎯 Квизов пройдено: {stats['quizzes_taken']}\n"
        f"✅ Квизов на 100%: {stats['quizzes_passed']}\n"
        f"🎁 Наград получено: {stats.get('rewards_received', 0)}\n"
        f"⏳ Наград в ожидании: {stats.get('rewards_pending', 0)}\n"
    )

    buttons = []
    if drinks_available > 0:
        buttons.append([InlineKeyboardButton(
            f"🍹 Обменять {cost} баллов на напиток",
            callback_data="request_reward"
        )])
    buttons.append([InlineKeyboardButton("🏅 Рейтинг", callback_data="leaderboard")])
    buttons.append([InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")])

    await query.message.edit_text(
        text, parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(buttons)
    )


async def request_reward_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Запрос на обмен баллов на напиток."""
    query = update.callback_query
    await query.answer()

    user = update.effective_user
    stats = db.get_user_stats(user.id)
    cost = get_settings().get('points_for_drink', 100)

    if not stats or stats['points'] < cost:
        await query.message.edit_text(
            f"❌ Недостаточно баллов!\n\n"
            f"У тебя: {stats['points'] if stats else 0} баллов\n"
            f"Нужно: {cost} баллов",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Профиль", callback_data="profile")]
            ])
        )
        return

    text = (
        f"🍹 <b>Обмен баллов на напиток</b>\n\n"
        f"Ты хочешь потратить <b>{cost} баллов</b>\n"
        f"и получить <b>1 бесплатный напиток</b>?\n\n"
        f"💎 Текущий баланс: {stats['points']} баллов\n"
        f"💎 После обмена: {stats['points'] - cost} баллов\n\n"
        f"⚠️ Запрос будет отправлен администратору для подтверждения."
    )

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Подтвердить", callback_data="confirm_reward"),
            InlineKeyboardButton("❌ Отмена", callback_data="profile"),
        ]
    ])

    await query.message.edit_text(text, parse_mode='HTML', reply_markup=keyboard)


async def confirm_reward_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Подтверждение запроса на награду."""
    query = update.callback_query
    await query.answer()

    user = update.effective_user
    stats = db.get_user_stats(user.id)
    cost = get_settings().get('points_for_drink', 100)

    if not stats or stats['points'] < cost:
        await query.message.edit_text("❌ Недостаточно баллов!")
        return

    reward_id = db.create_reward_request(user.id, cost)

    text = (
        f"✅ <b>Запрос отправлен!</b>\n\n"
        f"🎫 Номер запроса: #{reward_id}\n"
        f"🍹 Награда: 1 бесплатный напиток\n"
        f"💎 Списано: {cost} баллов\n\n"
        f"Администратор подтвердит твою награду.\n"
        f"Покажи этот номер официанту! 🙌"
    )

    # Уведомляем админа
    from config import ADMIN_ID
    if ADMIN_ID:
        try:
            admin_text = (
                f"🔔 <b>Новый запрос на награду!</b>\n\n"
                f"👤 {user.first_name} (@{user.username})\n"
                f"🎫 Запрос #{reward_id}\n"
                f"🍹 1 бесплатный напиток\n"
                f"💎 {cost} баллов"
            )
            await context.bot.send_message(
                ADMIN_ID, admin_text, parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("✅ Подтвердить", callback_data=f"adm_cr_{reward_id}"),
                        InlineKeyboardButton("❌ Отклонить", callback_data=f"adm_rr_{reward_id}"),
                    ]
                ])
            )
        except Exception:
            pass

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("👤 Профиль", callback_data="profile")],
        [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")],
    ])

    await query.message.edit_text(text, parse_mode='HTML', reply_markup=keyboard)


async def leaderboard_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать рейтинг."""
    query = update.callback_query
    await query.answer()

    leaders = db.get_leaderboard(10)

    if not leaders:
        text = "🏅 <b>Рейтинг пока пуст!</b>\n\nПройди квиз первым!"
    else:
        text = "🏅 <b>Рейтинг — Топ 10</b>\n\n"
        medals = ["🥇", "🥈", "🥉"]
        for i, leader in enumerate(leaders):
            medal = medals[i] if i < 3 else f"{i + 1}."
            name = leader['first_name'] or leader['username'] or '???'
            text += f"{medal} <b>{name}</b> — {leader['points']} баллов\n"

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Профиль", callback_data="profile")],
        [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")],
    ])

    await query.message.edit_text(text, parse_mode='HTML', reply_markup=keyboard)


def get_handlers():
    """Вернуть список хэндлеров."""
    return [
        CallbackQueryHandler(profile_callback, pattern="^profile$"),
        CallbackQueryHandler(request_reward_callback, pattern="^request_reward$"),
        CallbackQueryHandler(confirm_reward_callback, pattern="^confirm_reward$"),
        CallbackQueryHandler(leaderboard_callback, pattern="^leaderboard$"),
    ]
