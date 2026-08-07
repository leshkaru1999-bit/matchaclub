"""Конфигурация бота Matcha Club."""
import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID = int(os.getenv('ADMIN_ID') or '0')
ADMIN_USERNAME = os.getenv('ADMIN_USERNAME', 'Aleksey1906').lower().strip('@')
WEBAPP_URL = os.getenv('WEBAPP_URL', 'https://example.loca.lt')

# Пути к данным
DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')
PHOTOS_DIR = os.path.join(DATA_DIR, 'photos')
DB_PATH = os.path.join(os.path.dirname(__file__), 'matcha_club.db')

# Система баллов
import json

def get_settings():
    settings_path = os.path.join(DATA_DIR, 'settings.json')
    if os.path.exists(settings_path):
        with open(settings_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {'points_for_drink': 100}

POINTS_CORRECT = 1       # +1 за правильный ответ
POINTS_WRONG = -2        # -2 за неправильный ответ
# POINTS_FOR_DRINK теперь берется из get_settings()['points_for_drink']
QUIZ_COOLDOWN_HOURS = 24 # Кулдаун между квизами
QUIZ_QUESTIONS_COUNT = 15 # Количество вопросов в квизе
