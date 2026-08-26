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
AUDIO_DIR = os.path.join(DATA_DIR, 'audio')
DB_PATH = os.path.join(os.path.dirname(__file__), 'matcha_club.db')

# Система баллов
import json

def get_settings():
    settings_path = os.path.join(DATA_DIR, 'settings.json')
    defaults = {
        'points_for_drink': 100,
        'points_correct': 1,
        'points_wrong': -2,
        'quiz_cooldown_hours': 24,
        'quiz_questions_count': 15,
        'chat_id': ''
    }
    if os.path.exists(settings_path):
        try:
            with open(settings_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                defaults.update(data)
        except Exception as e:
            print(f"Error loading settings.json: {e}")
    return defaults
