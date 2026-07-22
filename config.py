"""Конфигурация бота Matcha Club."""
import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID = int(os.getenv('ADMIN_ID') or '0')
ADMIN_USERNAME = os.getenv('ADMIN_USERNAME', 'Aleksey1906').lower().strip('@')
WEBAPP_URL = os.getenv('WEBAPP_URL', 'https://example.loca.lt')

# Система баллов
POINTS_CORRECT = 1       # +1 за правильный ответ
POINTS_WRONG = -2        # -2 за неправильный ответ
POINTS_FOR_DRINK = 20    # 20 баллов = 1 напиток
QUIZ_COOLDOWN_HOURS = 24 # Кулдаун между квизами
QUIZ_QUESTIONS_COUNT = 15 # Количество вопросов в квизе

# Пути к данным
DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')
PHOTOS_DIR = os.path.join(DATA_DIR, 'photos')
DB_PATH = os.path.join(os.path.dirname(__file__), 'matcha_club.db')
