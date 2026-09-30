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

BRANCH_NAMES = {
    'tsum': 'ТСМ',
    'shevchenko': 'Шевченко',
    'forum': 'Форум',
    'itpark': 'Айти Парк',
    'foodmall': 'Фудмолл',
}

TASHKENT_TZ = datetime.timezone(datetime.timedelta(hours=5))


def _event_branches_label(ev):
    branches = ev.get('branches') or ['all']
    if 'all' in branches:
        return '🌍 Все филиалы'
    names = [BRANCH_NAMES.get(b, b) for b in branches]
    return '🏢 ' + ', '.join(names)


async def send_event_reminders(context: ContextTypes.DEFAULT_TYPE) -> int:
    """Напоминает в рабочем чате о событиях, которые состоятся завтра. Возвращает число отправленных сообщений."""
    events_path = os.path.join(DATA_DIR, 'events.json')
    if not os.path.exists(events_path):
        return 0
    try:
        with open(events_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f"Error loading events.json: {e}")
        return 0

    events = data.get('events', [])
    if not events:
        return 0

    tomorrow = (datetime.datetime.now(TASHKENT_TZ) + datetime.timedelta(days=1)).date()
    tomorrow_str = tomorrow.isoformat()
    matching = [e for e in events if e.get('date') == tomorrow_str]
    if not matching:
        return 0

    from config import get_settings
    settings = get_settings()
    chat_id = settings.get('chat_id')
    if not chat_id:
        return 0

    date_disp = tomorrow.strftime('%d.%m.%Y')
    sent = 0
    for ev in matching:
        emoji = ev.get('emoji', '📌')
        title = ev.get('title', 'Событие')
        time_str = ev.get('time', '')
        when = date_disp + (f", {time_str}" if time_str else "")
        text = (
            f"⏰ <b>Напоминание: завтра событие!</b>\n\n"
            f"{emoji} <b>{title}</b>\n"
            f"🗓 {when}\n"
            f"{_event_branches_label(ev)}"
        )
        if ev.get('description'):
            text += f"\n\n{ev['description']}"
        try:
            await context.bot.send_message(chat_id=chat_id, text=text, parse_mode='HTML')
            sent += 1
        except Exception as e:
            print(f"Failed to post event reminder to group {chat_id}: {e}")
    return sent


def setup_jobs(job_queue):
    # Факт дня — раз в день в 10:00
    job_queue.run_daily(send_random_fact, time=datetime.time(hour=10, minute=0, tzinfo=TASHKENT_TZ))
    # Напоминание о событиях на завтра — раз в день в 18:00
    job_queue.run_daily(send_event_reminders, time=datetime.time(hour=18, minute=0, tzinfo=TASHKENT_TZ))
