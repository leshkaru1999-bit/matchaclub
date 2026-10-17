import os
import json
import random
import time
import hmac
import hashlib
from urllib.parse import parse_qsl
import httpx
from fastapi import FastAPI, HTTPException, Request, Header, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import database as db
from config import DATA_DIR, PHOTOS_DIR, AUDIO_DIR

app = FastAPI(title="Matcha Club Mini App API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Запрещаем кэширование для HTML/JS/CSS ──────────────────────
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

class NoCacheMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        path = request.url.path
        if path.endswith(('.html', '.js', '.css')) or path == '/':
            response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            response.headers['Pragma'] = 'no-cache'
            response.headers['Expires'] = '0'
        return response

app.add_middleware(NoCacheMiddleware)

# ─── Проверка подписи Telegram initData ─────────────────────────
def verify_init_data(init_data: str, max_age_seconds: int = 86400) -> dict:
    """Проверяет HMAC-подпись initData от Telegram WebApp и возвращает данные пользователя.

    Алгоритм: https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
    """
    from config import BOT_TOKEN
    if not init_data:
        raise HTTPException(status_code=401, detail="Отсутствует initData")

    try:
        parsed = dict(parse_qsl(init_data, strict_parsing=True))
    except ValueError:
        raise HTTPException(status_code=401, detail="Некорректный initData")

    received_hash = parsed.pop('hash', None)
    if not received_hash:
        raise HTTPException(status_code=401, detail="initData без подписи")

    data_check_string = '\n'.join(f"{k}={v}" for k, v in sorted(parsed.items()))
    secret_key = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
    calculated_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(calculated_hash, received_hash):
        raise HTTPException(status_code=401, detail="Неверная подпись initData")

    auth_date = int(parsed.get('auth_date', 0))
    if time.time() - auth_date > max_age_seconds:
        raise HTTPException(status_code=401, detail="initData устарела, откройте приложение заново")

    user_json = parsed.get('user')
    if not user_json:
        raise HTTPException(status_code=401, detail="initData без данных пользователя")

    return json.loads(user_json)


async def get_verified_user(x_telegram_init_data: str = Header(None, alias="X-Telegram-Init-Data")) -> dict:
    return verify_init_data(x_telegram_init_data)


def ensure_owner(verified_user: dict, user_id: int):
    """Убеждаемся, что запрос сделан от лица владельца user_id, а не подделан."""
    if verified_user.get('id') != user_id:
        raise HTTPException(status_code=403, detail="user_id не совпадает с авторизованным пользователем")


# Актуальный маппинг блюд → файлы фото
PHOTO_MAP = {
    "Мини-киш с лососем и сыром": "mini_kish_salmon.jpg",
    "Вафля с яйцом пашот": "waffle_poached_egg.jpg",
    "Вафля сладкая": "waffle_sweet.jpg",
    "Вафля с грибами": "waffle_mushrooms.jpg",
    "Каша из цельного овса с ягодами": "oatmeal_berries.jpg",
    "Протеиновые сырники с ягодами": "syrniki_berries.jpg",
    "Белковый омлет с креветками": "omelet_shrimp.jpg",
    "Скрембл с лососем и овощными оладьями": "scramble_salmon.jpg",
    "Классический омлет с сыром": "omelet_classic.jpg",
    "Авокадо-тост с яйцом пашот и халуми": "avocado_toast.jpg",
    "Шакшука": "shakshuka.jpg",
    "Йогурт-боул с гранолой": "yogurt_bowl.jpg",
    "Чечевичный крем-суп с бараниной": "soup_lentil.jpg",
    "Крем-суп минестроне": "soup_minestrone.jpg",
    "Поке-боул с курицей": "poke_chicken.jpg",
    "Боул с курицей и киноа": "poke_chicken.jpg",
    "Поке-боул с лососем": "poke_salmon.jpg",
    "Боул с лососем слабой соли": "poke_salmon.jpg",
    "Поке-боул с говядиной": "poke_beef.jpg",
    "Фреш-ролл с курицей": "fresh_roll_chicken.jpg",
    "Фреш-ролл с ростбифом": "fresh_roll_beef.jpg",
    "Матча-фисташка": "media__1783960634273.jpg",
    "Печенье с фисташковым кремом": "media__1783960634294.jpg",
    "Печенье с финиками": "media__1783960634307.jpg",
}


class UserInit(BaseModel):
    id: int
    first_name: str
    username: str | None = None

class QuizAnswer(BaseModel):
    id: int
    selected: int

class QuizSubmit(BaseModel):
    user_id: int
    answers: list[QuizAnswer]

class RewardRequest(BaseModel):
    user_id: int

class AttendanceData(BaseModel):
    user_id: int
    first_name: str
    username: str | None = None
    action: str  # 'IN' or 'OUT'
    latitude: float
    longitude: float


def load_json(filename):
    path = os.path.join(DATA_DIR, filename)
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def extract_facts_list(data):
    """facts.json может быть списком фактов или {"facts": [...]}."""
    if isinstance(data, list):
        return data
    return data.get('facts', [])


def save_json(filename, data):
    path = os.path.join(DATA_DIR, filename)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


@app.post("/api/init_user")
async def init_user(user: UserInit, verified_user: dict = Depends(get_verified_user)):
    ensure_owner(verified_user, user.id)
    from config import get_settings
    db.get_or_create_user(user.id, user.username or "", user.first_name)
    stats = db.get_user_stats(user.id)
    cost = get_settings().get('points_for_drink', 100)
    return {"status": "ok", "stats": stats, "reward_cost": cost}


@app.get("/api/profile/{user_id}")
async def get_profile(user_id: int, verified_user: dict = Depends(get_verified_user)):
    ensure_owner(verified_user, user_id)
    from config import get_settings
    stats = db.get_user_stats(user_id)
    if not stats:
        raise HTTPException(status_code=404, detail="User not found")
    cost = get_settings().get('points_for_drink', 100)
    return {"stats": stats, "reward_cost": cost}


@app.get("/api/menu")
async def get_menu():
    menu_data = load_json('menu.json')
    if 'categories' in menu_data:
        for cat in menu_data['categories']:
            for item in cat.get('items', []):
                filename = item.get('photo') or PHOTO_MAP.get(item.get('name'))
                if filename:
                    photo_path = os.path.join(PHOTOS_DIR, filename)
                    if os.path.exists(photo_path):
                        item['photo_url'] = f"/api/photos/{filename}"
    return menu_data


@app.get("/api/welcome")
async def get_welcome():
    return load_json('welcome.json')


@app.get("/api/facts/random")
async def get_random_fact():
    data = load_json('facts.json')
    facts_list = extract_facts_list(data)
    if facts_list:
        return random.choice(facts_list)
    return {"text": "Факты не найдены"}


# Вопросы про КБЖУ (калории, белки, жиры, углеводы) в квиз не выдаём
import re as _re
_KBJU_QUESTION_RE = _re.compile(
    r'кбжу|калори|ккал|углевод|\bжир(ов|а|ы|ам)?\b|сколько[^?]*\bбелка\b|самое белков', _re.I)
_KBJU_ANSWER_RE = _re.compile(r'\d+\s*(г|гр|грамм|ккал)\b', _re.I)


def is_kbju_question(q):
    """Вопрос про КБЖУ: о них спрашивает сам вопрос или правильный ответ содержит граммы/ккал."""
    if _KBJU_QUESTION_RE.search(q.get('question', '')):
        return True
    opts = q.get('options', [])
    correct = q.get('correct')
    if isinstance(correct, int) and 0 <= correct < len(opts):
        return bool(_KBJU_ANSWER_RE.search(str(opts[correct])))
    return False


# Вопросы о времени приготовления/подачи блюд и напитков в квиз не выдаём
_PREP_TIME_RE = _re.compile(r'сколько времени|врем\w*\s+(приготовлен|готов|подач)', _re.I)
_MINUTES_ANSWER_RE = _re.compile(r'^\s*\d+\s*[-–]\s*\d+\s*мин', _re.I)


def is_prep_time_question(q):
    if _PREP_TIME_RE.search(q.get('question', '')):
        return True
    opts = q.get('options', [])
    correct = q.get('correct')
    return isinstance(correct, int) and 0 <= correct < len(opts) and bool(_MINUTES_ANSWER_RE.search(str(opts[correct])))


# Вопросы по велком-буку в квиз не выдаём
WELCOME_BOOK_CATEGORIES = {
    'о компании', 'о компании & миссия', 'философия', 'днк компании', 'ценности', 'кодекс сотрудника',
}


def is_excluded_question(q):
    return (is_kbju_question(q) or is_prep_time_question(q)
            or (q.get('category') or '').strip().lower() in WELCOME_BOOK_CATEGORIES)


@app.get("/api/quiz")
async def get_quiz():
    from config import get_settings
    data = load_json('quiz.json')
    data['questions'] = [q for q in data.get('questions', []) if not is_excluded_question(q)]
    s = get_settings()
    # Правила подсчёта — те же, по которым /api/quiz/submit начисляет баллы
    data['scoring'] = {
        'correct': s.get('points_correct', 1),
        'wrong': s.get('points_wrong', -2),
        'drink': s.get('points_for_drink', 100),
    }
    return data


@app.get("/api/tour")
async def get_tour():
    return load_json('tour.json')


@app.get("/api/trainings")
async def get_trainings():
    return load_json('trainings.json')


@app.get("/api/products")
async def get_products():
    """Справочник продуктов (content/products.json) + блюда меню, где продукт используется."""
    import re
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'content', 'products.json')
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    dishes = []
    for cat in load_json('menu.json').get('categories', []):
        for item in cat.get('items', []):
            text = (item.get('ingredients') or '').strip() or item.get('name', '')
            dishes.append((item.get('name', '').strip().rstrip('.'), text.lower()))
    for p in data['products']:
        pats = [re.compile(r'(?<![а-яёa-z])' + m, re.I) for m in p.get('match', [])]
        p['dishes'] = sorted({name for name, text in dishes if any(r.search(text) for r in pats)})
        p.pop('match', None)
    return data


@app.get("/api/events")
async def get_events():
    from events_util import expand_events
    data = load_json('events.json')
    return {"events": expand_events(data.get('events', []))}


@app.get("/api/branches")
async def get_branches():
    return load_json('branches.json')


@app.post("/api/quiz/submit")
async def submit_quiz(data: QuizSubmit, verified_user: dict = Depends(get_verified_user)):
    ensure_owner(verified_user, data.user_id)
    from config import get_settings
    settings = get_settings()
    pts_correct = settings.get('points_correct', 1)
    pts_wrong = settings.get('points_wrong', -2)

    quiz_data = load_json('quiz.json')
    questions_by_id = {q['id']: q for q in quiz_data.get('questions', [])}

    correct_answers = 0
    wrong_answers = 0
    for ans in data.answers:
        q = questions_by_id.get(ans.id)
        if not q:
            continue
        if ans.selected == q.get('correct'):
            correct_answers += 1
        else:
            wrong_answers += 1

    total = correct_answers + wrong_answers
    points_earned = max(0, (correct_answers * pts_correct) + (wrong_answers * pts_wrong))
    score_percentage = 100 if wrong_answers == 0 else int(
        (correct_answers / total) * 100) if total > 0 else 0

    if points_earned != 0:
        db.update_user_points(data.user_id, points_earned)
    db.add_quiz_result(data.user_id, score_percentage, total, points_earned)
    return {
        "status": "ok",
        "new_stats": db.get_user_stats(data.user_id),
        "correct_answers": correct_answers,
        "wrong_answers": wrong_answers,
        "points_earned": points_earned,
    }


@app.get("/api/leaderboard")
async def get_leaderboard():
    leaders = db.get_leaderboard(10)
    return {"leaders": leaders}


@app.post("/api/reward/request")
async def request_reward(req: RewardRequest, verified_user: dict = Depends(get_verified_user)):
    ensure_owner(verified_user, req.user_id)
    from config import get_settings
    cost = get_settings().get('points_for_drink', 100)
    stats = db.get_user_stats(req.user_id)
    if not stats or stats['points'] < cost:
        raise HTTPException(status_code=400, detail="Недостаточно баллов")
    reward_id = db.create_reward_request(req.user_id, cost)
    return {"status": "ok", "reward_id": reward_id, "new_points": stats['points'] - cost}


@app.post("/api/attendance")
async def log_attendance(data: AttendanceData, verified_user: dict = Depends(get_verified_user)):
    ensure_owner(verified_user, data.user_id)
    from config import BOT_TOKEN, ADMIN_ID
    # Записываем в БД
    db.log_attendance(data.user_id, data.latitude, data.longitude, data.action)
    
    # Отправляем уведомление админу
    if ADMIN_ID and BOT_TOKEN:
        action_text = "🟢 ПРИХОД" if data.action == 'IN' else "🔴 УХОД"
        admin_text = (
            f"🚨 <b>Отметка на смене (Mini App)! ({action_text})</b>\n\n"
            f"👤 Сотрудник: <b>{data.first_name}</b> (@{data.username or '—'})\n"
            f"🆔 ID: <code>{data.user_id}</code>\n"
        )
        url_msg = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        url_loc = f"https://api.telegram.org/bot{BOT_TOKEN}/sendLocation"
        
        try:
            async with httpx.AsyncClient() as client:
                await client.post(url_msg, json={"chat_id": ADMIN_ID, "text": admin_text, "parse_mode": "HTML"})
                await client.post(url_loc, json={"chat_id": ADMIN_ID, "latitude": data.latitude, "longitude": data.longitude})
        except Exception as e:
            print(f"Ошибка при отправке локации админу: {e}")
            
    return {"status": "ok"}


@app.get("/api/fact")
async def get_fact():
    import random
    fact = ""
    
    facts_path = os.path.join(DATA_DIR, 'facts.json')
    if os.path.exists(facts_path):
        try:
            with open(facts_path, 'r', encoding='utf-8') as f:
                facts_data = json.load(f)
            facts_list = extract_facts_list(facts_data)
            if facts_list:
                item = random.choice(facts_list)
                emoji = item.get('emoji', '💡')
                fact = f"{emoji} <b>Факт дня</b><br><br>{item.get('text', '')}"
        except Exception as e:
            print(f"Error loading facts.json: {e}")
                
    if not fact:
        fact = "Сегодня отличный день для новой чашки матчи!"
        
    return {"fact_html": fact}

# ─── Монтируем статику ──────────────────────────────────────────
os.makedirs(os.path.join(os.path.dirname(__file__), 'static'), exist_ok=True)
os.makedirs(PHOTOS_DIR, exist_ok=True)
os.makedirs(AUDIO_DIR, exist_ok=True)
app.mount("/api/photos", StaticFiles(directory=PHOTOS_DIR), name="photos")
app.mount("/api/audio", StaticFiles(directory=AUDIO_DIR), name="audio")
app.mount("/", StaticFiles(directory="static", html=True), name="static")
