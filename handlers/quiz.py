"""Обработчик квиза с системой баллов."""
import json
import os
import random
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CallbackQueryHandler
import database as db
from config import get_settings


def load_quiz():
    """Загрузить вопросы квиза."""
    path = os.path.join(DATA_DIR, 'quiz.json')
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


async def quiz_start_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало квиза."""
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id

    # Проверяем кулдаун
    last_time = db.get_last_quiz_time(user_id)
    if last_time:
        cooldown_end = last_time + timedelta(hours=get_settings().get('quiz_cooldown_hours', 24))
        if datetime.now() < cooldown_end:
            remaining = cooldown_end - datetime.now()
            hours = int(remaining.total_seconds() // 3600)
            minutes = int((remaining.total_seconds() % 3600) // 60)
            await query.message.edit_text(
                f"⏳ <b>Квиз на перезарядке!</b>\n\n"
                f"Следующий квиз будет доступен через:\n"
                f"⏰ <b>{hours}ч {minutes}мин</b>\n\n"
                f"А пока изучай меню и велкам-бук! 📖",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")]
                ])
            )
            return

    # Загружаем и перемешиваем вопросы
    data = load_quiz()
    questions = data['questions'][:]
    random.shuffle(questions)
    questions = questions[:get_settings().get('quiz_questions_count', 15)]

    # Сохраняем состояние квиза в context.user_data
    context.user_data['quiz'] = {
        'questions': questions,
        'current': 0,
        'score': 0,
        'wrong': 0,
        'answers': [],
    }

    text = (
        f"🎯 <b>Квиз Matcha Club</b>\n\n"
        f"📋 Вопросов: <b>{len(questions)}</b>\n"
        f"✅ Правильный ответ: <b>+{get_settings().get('points_correct', 1)} балл</b>\n"
        f"❌ Неправильный ответ: <b>{get_settings().get('points_wrong', -2)} балла</b>\n"
        f"🍹 <b>20 баллов</b> = 1 бесплатный напиток\n\n"
        f"Готов? Поехали! 🚀"
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("▶️ Начать", callback_data="quiz_go")],
        [InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")],
    ])

    await query.message.edit_text(text, parse_mode='HTML', reply_markup=keyboard)


async def quiz_go_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать текущий вопрос."""
    query = update.callback_query
    await query.answer()

    quiz = context.user_data.get('quiz')
    if not quiz:
        await query.message.edit_text("❌ Квиз не найден. Начни заново.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🎯 Начать квиз", callback_data="quiz_start")]
            ]))
        return

    await show_question(query.message, quiz)


async def show_question(message, quiz):
    """Показать вопрос квиза."""
    idx = quiz['current']
    total = len(quiz['questions'])
    q = quiz['questions'][idx]

    # Прогресс бар
    filled = int((idx / total) * 10)
    progress = "▓" * filled + "░" * (10 - filled)

    text = (
        f"❓ <b>Вопрос {idx + 1} из {total}</b>\n"
        f"[{progress}]\n\n"
        f"<b>{q['question']}</b>"
    )

    buttons = []
    labels = ['🅰️', '🅱️', '🅲', '🅳']
    for i, option in enumerate(q['options']):
        buttons.append([InlineKeyboardButton(
            f"{labels[i]} {option}",
            callback_data=f"qa_{idx}_{i}"
        )])

    await message.edit_text(
        text,
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(buttons)
    )


async def quiz_answer_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ответа на вопрос."""
    query = update.callback_query

    quiz = context.user_data.get('quiz')
    if not quiz:
        await query.answer("Квиз не найден!")
        return

    parts = query.data.replace("qa_", "").split("_")
    q_idx = int(parts[0])
    a_idx = int(parts[1])

    # Защита от повторного ответа
    if q_idx != quiz['current']:
        await query.answer("Ты уже ответил на этот вопрос!")
        return

    await query.answer()

    q = quiz['questions'][q_idx]
    is_correct = a_idx == q['correct']

    if is_correct:
        quiz['score'] += 1
        result_emoji = "✅"
        result_text = f"Правильно! +{get_settings().get('points_correct', 1)} балл"
    else:
        quiz['wrong'] += 1
        result_emoji = "❌"
        correct_label = ['🅰️', '🅱️', '🅲', '🅳'][q['correct']]
        result_text = f"Неправильно! {get_settings().get('points_wrong', -2)} балла\nПравильный ответ: {correct_label} {q['options'][q['correct']]}"

    quiz['answers'].append(is_correct)
    quiz['current'] += 1

    text = (
        f"{result_emoji} <b>{result_text}</b>\n\n"
        f"💬 {q['explanation']}\n\n"
        f"📊 Счёт: {quiz['score']}/{q_idx + 1}"
    )

    # Проверяем, есть ли ещё вопросы
    if quiz['current'] < len(quiz['questions']):
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("➡️ Следующий вопрос", callback_data="quiz_go")]
        ])
        await query.message.edit_text(text, parse_mode='HTML', reply_markup=keyboard)
    else:
        # Квиз завершён — показываем результаты
        await finish_quiz(query.message, quiz, update.effective_user.id)


async def finish_quiz(message, quiz, user_id):
    """Завершение квиза и начисление баллов."""
    total = len(quiz['questions'])
    score = quiz['score']
    wrong = quiz['wrong']

    # Подсчёт баллов: +1 за правильный, -2 за неправильный, минимум 0
    pts_correct = get_settings().get('points_correct', 1)
    pts_wrong = get_settings().get('points_wrong', -2)
    points_earned = max(0, (score * pts_correct) + (wrong * pts_wrong))

    # Сохраняем в БД
    db.add_quiz_result(user_id, score, total, points_earned)
    new_balance = db.update_user_points(user_id, points_earned)

    # Определяем оценку
    pct = (score / total) * 100
    if pct == 100:
        grade = "🏆 ИДЕАЛЬНО!"
    elif pct >= 80:
        grade = "⭐ Отлично!"
    elif pct >= 60:
        grade = "👍 Хорошо!"
    elif pct >= 40:
        grade = "📚 Неплохо, но стоит подучить"
    else:
        grade = "📖 Нужно больше изучать материал"

    text = (
        f"🏁 <b>Квиз завершён!</b>\n\n"
        f"{grade}\n\n"
        f"📊 <b>Результат:</b>\n"
        f"✅ Правильных: {score}/{total}\n"
        f"❌ Неправильных: {wrong}/{total}\n\n"
        f"💰 <b>Заработано: +{points_earned} баллов</b>\n"
        f"💎 Баланс: <b>{new_balance} баллов</b>\n\n"
    )

    if new_balance >= 20:
        text += f"🍹 У тебя достаточно баллов для напитка! Зайди в Профиль, чтобы обменять.\n"

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("👤 Профиль", callback_data="profile")],
        [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")],
    ])

    await message.edit_text(text, parse_mode='HTML', reply_markup=keyboard)


def get_handlers():
    """Вернуть список хэндлеров."""
    return [
        CallbackQueryHandler(quiz_start_callback, pattern="^quiz_start$"),
        CallbackQueryHandler(quiz_go_callback, pattern="^quiz_go$"),
        CallbackQueryHandler(quiz_answer_callback, pattern="^qa_"),
    ]
