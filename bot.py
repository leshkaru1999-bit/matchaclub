"""
Matcha Club Telegram Bot
Бот для сотрудников Matcha Club & Mari Wellness.
Велкам-бук, меню с КБЖУ, квиз с баллами, факты о здоровом питании.
"""
import asyncio
import logging
from telegram.ext import Application
import database as db
from config import BOT_TOKEN
from handlers import start, welcome, menu, quiz, profile, facts, admin, attendance

# Логирование
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


def main():
    """Запуск бота."""
    # Инициализация БД
    db.init_db()
    logger.info("✅ База данных инициализирована")

    # Академия: применяем новую версию тренингов и вопросов квиза (если вышла)
    try:
        from academy.build import sync_if_new
        if sync_if_new():
            logger.info("🎓 Академия Matcha Club обновлена")
    except Exception as e:
        logger.error(f"⚠️ Не удалось обновить Академию: {e}")

    # События: один раз добавляем серию «Повторение воскресного тренинга» по четвергам
    try:
        from config import DATA_DIR
        from events_util import seed_default_events
        if seed_default_events(DATA_DIR):
            logger.info("🔁 Добавлено событие: повторение тренинга каждый четверг")
    except Exception as e:
        logger.error(f"⚠️ Не удалось добавить повторяющееся событие: {e}")

    if not BOT_TOKEN:
        logger.error("❌ BOT_TOKEN не задан в .env!")
        return

    # Совместимость с Python 3.14+
    try:
        asyncio.get_event_loop()
    except RuntimeError:
        asyncio.set_event_loop(asyncio.new_event_loop())

    # Запускаем FastAPI в фоне
    import subprocess
    import sys
    logger.info("🚀 Запуск FastAPI сервера (Mini App API)...")
    subprocess.Popen([sys.executable, "-m", "uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"])

    # Создание приложения
    app = Application.builder().token(BOT_TOKEN).build()

    import publisher
    publisher.setup_jobs(app.job_queue)

    # Регистрация обработчиков (порядок важен!)
    # 1. Команды
    for handler in start.get_handlers():
        app.add_handler(handler)

    # 2. Велкам-бук
    for handler in welcome.get_handlers():
        app.add_handler(handler)

    # 3. Меню
    for handler in menu.get_handlers():
        app.add_handler(handler)

    # 4. Квиз
    for handler in quiz.get_handlers():
        app.add_handler(handler)

    # 5. Профиль и награды
    for handler in profile.get_handlers():
        app.add_handler(handler)

    # 6. Факты
    for handler in facts.get_handlers():
        app.add_handler(handler)

    # 7. Админ-панель (последним, т.к. содержит MessageHandler)
    for handler in admin.get_handlers():
        app.add_handler(handler)
        
    # 8. Отметка на смене (геолокация)
    for handler in attendance.get_handlers():
        app.add_handler(handler)

    # Запуск
    logger.info("🍵 Matcha Club Bot запущен!")
    app.run_polling(drop_pending_updates=True)


if __name__ == '__main__':
    main()
