import random
import datetime
import json
import os
from telegram.ext import ContextTypes
from config import DATA_DIR
import database as db

async def send_random_fact(context: ContextTypes.DEFAULT_TYPE):
    fact = ""
    facts_path = os.path.join(DATA_DIR, 'facts.json')
    if os.path.exists(facts_path):
        try:
            with open(facts_path, 'r', encoding='utf-8') as f:
                facts_data = json.load(f)
            facts_list = facts_data if isinstance(facts_data, list) else facts_data.get('facts', [])
            if facts_list:
                item = random.choice(facts_list)
                emoji = item.get('emoji', '💡')
                fact = f"{emoji} <b>Факт дня</b>\n\n{item.get('text', '')}"
        except Exception as e:
            print(f"Error loading facts.json: {e}")
            
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
