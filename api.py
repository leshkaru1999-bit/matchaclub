import os
import json
import random
import httpx
from fastapi import FastAPI, HTTPException, Request
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

class QuizSubmit(BaseModel):
    user_id: int
    correct_answers: int
    wrong_answers: int
    points_earned: int

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


def save_json(filename, data):
    path = os.path.join(DATA_DIR, filename)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


@app.post("/api/init_user")
async def init_user(user: UserInit):
    from config import get_settings
    db.get_or_create_user(user.id, user.username or "", user.first_name)
    stats = db.get_user_stats(user.id)
    cost = get_settings().get('points_for_drink', 100)
    return {"status": "ok", "stats": stats, "reward_cost": cost}


@app.get("/api/profile/{user_id}")
async def get_profile(user_id: int):
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
    if 'facts' in data and data['facts']:
        return random.choice(data['facts'])
    return {"text": "Факты не найдены"}


@app.get("/api/quiz")
async def get_quiz():
    return load_json('quiz.json')


@app.get("/api/tour")
async def get_tour():
    return load_json('tour.json')


@app.post("/api/quiz/submit")
async def submit_quiz(data: QuizSubmit):
    points_change = data.points_earned
    if points_change != 0:
        db.update_user_points(data.user_id, points_change)
    total = data.correct_answers + data.wrong_answers
    score_percentage = 100 if data.wrong_answers == 0 else int(
        (data.correct_answers / total) * 100) if total > 0 else 0
    db.add_quiz_result(data.user_id, score_percentage, total, data.points_earned)
    return {"status": "ok", "new_stats": db.get_user_stats(data.user_id)}


@app.get("/api/leaderboard")
async def get_leaderboard():
    leaders = db.get_leaderboard(10)
    return {"leaders": leaders}


@app.post("/api/reward/request")
async def request_reward(req: RewardRequest):
    from config import get_settings
    cost = get_settings().get('points_for_drink', 100)
    stats = db.get_user_stats(req.user_id)
    if not stats or stats['points'] < cost:
        raise HTTPException(status_code=400, detail="Недостаточно баллов")
    reward_id = db.create_reward_request(req.user_id, cost)
    return {"status": "ok", "reward_id": reward_id, "new_points": stats['points'] - cost}


@app.post("/api/attendance")
async def log_attendance(data: AttendanceData):
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
            facts_list = facts_data.get('facts', [])
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
