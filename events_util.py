"""Повторяющиеся события.

В events.json событие может иметь:
  "repeat": "weekly"  — повторяется каждую неделю в тот же день недели, что и "date" (первое занятие);
  "recap": true       — «повторение тренинга»: название берётся из тренинга (type=training),
                        который прошёл в ближайшее воскресенье перед этой датой.

expand_events() превращает серии в конкретные даты — их видят Mini App и напоминания.
"""
import datetime
import json
import os

TASHKENT_TZ = datetime.timezone(datetime.timedelta(hours=5))

EVERY_WEEKDAY = ['каждый понедельник', 'каждый вторник', 'каждую среду', 'каждый четверг',
                 'каждую пятницу', 'каждую субботу', 'каждое воскресенье']


def today_local():
    return datetime.datetime.now(TASHKENT_TZ).date()


def is_weekly(ev):
    return ev.get('repeat') == 'weekly'


def every_label(ev):
    """'каждый четверг' для серии."""
    try:
        wd = datetime.date.fromisoformat(ev['date']).weekday()
    except (KeyError, ValueError):
        return 'каждую неделю'
    return EVERY_WEEKDAY[wd]


def recap_source(events, occ_date):
    """Тренинг в ближайшее воскресенье до occ_date (не серия)."""
    days_back = (occ_date.weekday() - 6) % 7 or 7
    sunday = (occ_date - datetime.timedelta(days=days_back)).isoformat()
    for ev in events:
        if not is_weekly(ev) and ev.get('type') == 'training' and ev.get('date') == sunday:
            return ev
    return None


def _recap_fill(occ, series, events, occ_date):
    src = recap_source(events, occ_date)
    if src:
        topic = src.get('title', '').strip()
        sunday = datetime.date.fromisoformat(src['date']).strftime('%d.%m')
        occ['title'] = f"Повторение: {topic}"
        base = f"Повторяем тему воскресного тренинга ({sunday}): «{topic}»."
    else:
        occ['title'] = series.get('title') or 'Повторение воскресного тренинга'
        base = "Повторяем тему, пройденную на тренинге в воскресенье."
    extra = series.get('description', '').strip()
    occ['description'] = f"{base}\n{extra}" if extra else base


def expand_events(events, today=None, weeks_back=4, weeks_ahead=8):
    """Список событий, где каждая серия развернута в конкретные даты (окно вокруг today)."""
    today = today or today_local()
    lo = today - datetime.timedelta(weeks=weeks_back)
    hi = today + datetime.timedelta(weeks=weeks_ahead)
    out = []
    for ev in events:
        if not is_weekly(ev):
            out.append(ev)
            continue
        try:
            start = datetime.date.fromisoformat(ev['date'])
        except (KeyError, ValueError):
            continue
        d = start
        if lo > start:
            d = start + datetime.timedelta(days=((lo - start).days + 6) // 7 * 7)
        while d <= hi:
            occ = dict(ev)
            occ['date'] = d.isoformat()
            occ['series_id'] = ev.get('id')
            occ['recurring'] = True
            if ev.get('recap'):
                _recap_fill(occ, ev, events, d)
            out.append(occ)
            d += datetime.timedelta(days=7)
    return out


# ---------- начальные события (добавляются один раз) ----------
SEED_KEY = 'thursday_recap_v1'


def _next_weekday(from_date, weekday):
    return from_date + datetime.timedelta(days=(weekday - from_date.weekday()) % 7)


def seed_default_events(data_dir):
    """Один раз добавляет серию «Повторение воскресного тренинга» по четвергам.
    Если админ потом удалит её — она не вернётся (флаг в events.json → seeded)."""
    path = os.path.join(data_dir, 'events.json')
    try:
        with open(path, encoding='utf-8') as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        data = {"events": []}
    seeded = data.setdefault('seeded', [])
    if SEED_KEY in seeded:
        return False
    events = data.setdefault('events', [])
    today = today_local()
    events.append({
        "id": "evt_thursday_recap",
        "type": "training",
        "emoji": "🔁",
        "title": "Повторение воскресного тренинга",
        "date": _next_weekday(today, 3).isoformat(),  # ближайший четверг
        "time": "15:00",
        "description": "",
        "branches": ["all"],
        "repeat": "weekly",
        "recap": True,
    })
    seeded.append(SEED_KEY)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    return True
