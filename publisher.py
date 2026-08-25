import random
import datetime
import json
import os
from telegram.ext import ContextTypes
from config import DATA_DIR
import database as db

async def send_random_fact(context: ContextTypes.DEFAULT_TYPE):
    # Get random fact from menu or welcome book
    fact = ""
    # We will pick randomly: 0 - menu fact, 1 - welcome book fact
    source = random.choice([0, 1])
    
    if source == 0:
        # Get from menu
        menu_path = os.path.join(DATA_DIR, 'menu.json')
        if os.path.exists(menu_path):
            with open(menu_path, 'r', encoding='utf-8') as f:
                menu_data = json.load(f)
            items = []
            for c in menu_data.get('categories', []):
                items.extend(c.get('items', []))
            if items:
                item = random.choice(items)
                fact = f"🍵 <b>Интересный факт о нашем меню!</b>\n\n<b>{item.get('name', 'Блюдо')}</b>\n{item.get('description', '')}\n\n<i>Заходи в Mini App, чтобы заказать или посмотреть детали!</i>"
    
    if not fact:
        # Get from tour
        tour_path = os.path.join(DATA_DIR, 'tour.json')
        if os.path.exists(tour_path):
            with open(tour_path, 'r', encoding='utf-8') as f:
                tour_data = json.load(f)
            sections = tour_data.get('sections', [])
            if sections:
                sec = random.choice(sections)
                fact = f"✨ <b>А ты знал?</b>\n\n<b>{sec.get('title', 'Интересно')}</b>\n{sec.get('text', '')}"
                
    if not fact:
        return
        
    from config import get_settings
    settings = get_settings()
    chat_id = settings.get('chat_id')
    
    if chat_id:
        try:
            await context.bot.send_message(chat_id=chat_id, text=fact, parse_mode='HTML')
        except Exception as e:
            print(f"Failed to post daily fact to group {chat_id}: {e}")

def setup_jobs(job_queue):
    # Send once a day at 10:00
    times = [
        datetime.time(hour=10, minute=0, tzinfo=datetime.timezone(datetime.timedelta(hours=5))) # Yekaterinburg/Tashkent time UTC+5
    ]
    for t in times:
        job_queue.run_daily(send_random_fact, time=t)
