"""База данных SQLite для бота Matcha Club."""
import sqlite3
from datetime import datetime
from config import DB_PATH


def get_connection():
    """Получить соединение с БД."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Инициализация таблиц БД."""
    conn = get_connection()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        first_name TEXT,
        points INTEGER DEFAULT 0,
        quizzes_taken INTEGER DEFAULT 0,
        quizzes_passed INTEGER DEFAULT 0,
        registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS quiz_results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        score INTEGER,
        total INTEGER,
        points_earned INTEGER,
        taken_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(user_id)
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS rewards (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        reward_type TEXT DEFAULT 'drink',
        points_spent INTEGER,
        status TEXT DEFAULT 'pending',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        confirmed_at TIMESTAMP,
        confirmed_by INTEGER,
        FOREIGN KEY (user_id) REFERENCES users(user_id)
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS attendance (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        latitude REAL,
        longitude REAL,
        action_type TEXT DEFAULT 'IN',
        checked_in_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(user_id)
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS admins (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        first_name TEXT,
        role TEXT DEFAULT 'full',
        added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        added_by INTEGER
    )''')
    # Миграция: добавляем role если столбца нет
    try:
        c.execute('ALTER TABLE admins ADD COLUMN role TEXT DEFAULT "full"')
    except Exception:
        pass
    conn.commit()
    conn.close()


def get_or_create_user(user_id: int, username: str = None, first_name: str = None) -> dict:
    """Получить или создать пользователя."""
    conn = get_connection()
    c = conn.cursor()
    c.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    user = c.fetchone()
    if not user:
        c.execute(
            'INSERT INTO users (user_id, username, first_name) VALUES (?, ?, ?)',
            (user_id, username, first_name)
        )
        conn.commit()
        c.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
        user = c.fetchone()
    else:
        # Обновляем данные пользователя
        c.execute(
            'UPDATE users SET username = ?, first_name = ? WHERE user_id = ?',
            (username, first_name, user_id)
        )
        conn.commit()
    result = dict(user)
    conn.close()
    return result


def update_user_points(user_id: int, points_change: int) -> int:
    """Обновить баллы пользователя. Возвращает новый баланс."""
    conn = get_connection()
    c = conn.cursor()
    c.execute('SELECT points FROM users WHERE user_id = ?', (user_id,))
    row = c.fetchone()
    if row:
        new_points = max(0, row['points'] + points_change)
        c.execute('UPDATE users SET points = ? WHERE user_id = ?', (new_points, user_id))
        conn.commit()
    else:
        new_points = 0
    conn.close()
    return new_points


def add_quiz_result(user_id: int, score: int, total: int, points_earned: int):
    """Добавить результат квиза."""
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        'INSERT INTO quiz_results (user_id, score, total, points_earned) VALUES (?, ?, ?, ?)',
        (user_id, score, total, points_earned)
    )
    c.execute(
        'UPDATE users SET quizzes_taken = quizzes_taken + 1 WHERE user_id = ?',
        (user_id,)
    )
    if score == total:
        c.execute(
            'UPDATE users SET quizzes_passed = quizzes_passed + 1 WHERE user_id = ?',
            (user_id,)
        )
    conn.commit()
    conn.close()


def get_user_stats(user_id: int) -> dict:
    """Получить статистику пользователя."""
    conn = get_connection()
    c = conn.cursor()
    c.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    user = c.fetchone()
    if not user:
        conn.close()
        return None
    result = dict(user)
    # Считаем награды
    c.execute(
        'SELECT COUNT(*) as cnt FROM rewards WHERE user_id = ? AND status = ?',
        (user_id, 'confirmed')
    )
    result['rewards_received'] = c.fetchone()['cnt']
    c.execute(
        'SELECT COUNT(*) as cnt FROM rewards WHERE user_id = ? AND status = ?',
        (user_id, 'pending')
    )
    result['rewards_pending'] = c.fetchone()['cnt']
    conn.close()
    return result


def get_last_quiz_time(user_id: int):
    """Получить время последнего квиза."""
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        'SELECT taken_at FROM quiz_results WHERE user_id = ? ORDER BY taken_at DESC LIMIT 1',
        (user_id,)
    )
    row = c.fetchone()
    conn.close()
    if row:
        return datetime.fromisoformat(row['taken_at'])
    return None


def create_reward_request(user_id: int, points_spent: int) -> int:
    """Создать запрос на награду. Возвращает ID."""
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        'INSERT INTO rewards (user_id, points_spent) VALUES (?, ?)',
        (user_id, points_spent)
    )
    reward_id = c.lastrowid
    # Списываем баллы
    c.execute(
        'UPDATE users SET points = points - ? WHERE user_id = ?',
        (points_spent, user_id)
    )
    conn.commit()
    conn.close()
    return reward_id


def get_pending_rewards() -> list:
    """Получить список ожидающих наград."""
    conn = get_connection()
    c = conn.cursor()
    c.execute('''
        SELECT r.id, r.user_id, r.points_spent, r.created_at,
               u.first_name, u.username
        FROM rewards r JOIN users u ON r.user_id = u.user_id
        WHERE r.status = 'pending'
        ORDER BY r.created_at
    ''')
    results = [dict(row) for row in c.fetchall()]
    conn.close()
    return results


def confirm_reward(reward_id: int, admin_id: int):
    """Подтвердить выдачу награды."""
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        'UPDATE rewards SET status = ?, confirmed_at = ?, confirmed_by = ? WHERE id = ?',
        ('confirmed', datetime.now().isoformat(), admin_id, reward_id)
    )
    conn.commit()
    conn.close()


def reject_reward(reward_id: int, admin_id: int):
    """Отклонить награду и вернуть баллы."""
    conn = get_connection()
    c = conn.cursor()
    c.execute('SELECT user_id, points_spent FROM rewards WHERE id = ?', (reward_id,))
    row = c.fetchone()
    if row:
        c.execute(
            'UPDATE users SET points = points + ? WHERE user_id = ?',
            (row['points_spent'], row['user_id'])
        )
        c.execute(
            'UPDATE rewards SET status = ?, confirmed_at = ?, confirmed_by = ? WHERE id = ?',
            ('rejected', datetime.now().isoformat(), admin_id, reward_id)
        )
    conn.commit()
    conn.close()


def get_leaderboard(limit: int = 10) -> list:
    """Получить топ пользователей по баллам."""
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        'SELECT user_id, first_name, username, points, quizzes_taken FROM users ORDER BY points DESC LIMIT ?',
        (limit,)
    )
    results = [dict(row) for row in c.fetchall()]
    conn.close()
    return results


def get_all_users() -> list:
    """Получить всех пользователей."""
    conn = get_connection()
    c = conn.cursor()
    c.execute('SELECT user_id FROM users')
    results = [row['user_id'] for row in c.fetchall()]
    conn.close()
    return results


def get_all_users_count() -> int:
    """Получить количество пользователей."""
    conn = get_connection()
    c = conn.cursor()
    c.execute('SELECT COUNT(*) as cnt FROM users')
    cnt = c.fetchone()['cnt']
    conn.close()
    return cnt


def log_attendance(user_id: int, lat: float, lon: float, action_type: str = 'IN'):
    """Отметить приход или уход со смены."""
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        'INSERT INTO attendance (user_id, latitude, longitude, action_type) VALUES (?, ?, ?, ?)',
        (user_id, lat, lon, action_type)
    )
    conn.commit()
    conn.close()

def get_recent_attendance(limit: int = 20):
    conn = get_connection()
    c = conn.cursor()
    c.execute('''
        SELECT a.*, u.first_name, u.username
        FROM attendance a
        LEFT JOIN users u ON a.user_id = u.user_id
        ORDER BY a.checked_in_at DESC
        LIMIT ?
    ''', (limit,))
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


# ─── Администраторы ───────────────────────────────────────

def get_db_admins() -> list:
    """Вернуть всех админов из БД."""
    conn = get_connection()
    c = conn.cursor()
    c.execute('SELECT * FROM admins ORDER BY added_at DESC')
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


def is_db_admin(user_id: int) -> bool:
    """Проверить есть ли пользователь админ в БД."""
    conn = get_connection()
    c = conn.cursor()
    c.execute('SELECT 1 FROM admins WHERE user_id = ?', (user_id,))
    result = c.fetchone() is not None
    conn.close()
    return result


def add_db_admin(user_id: int, username: str, first_name: str, added_by: int, role: str = 'full') -> bool:
    """Добавить админа в БД. Возвращает True если добавлен, False если уже есть."""
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute(
            'INSERT INTO admins (user_id, username, first_name, role, added_by) VALUES (?, ?, ?, ?, ?)',
            (user_id, username, first_name, role, added_by)
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


def remove_db_admin(user_id: int) -> bool:
    """Удалить админа из БД."""
    conn = get_connection()
    c = conn.cursor()
    c.execute('DELETE FROM admins WHERE user_id = ?', (user_id,))
    deleted = c.rowcount > 0
    conn.commit()
    conn.close()
    return deleted


def get_admin_role(user_id: int) -> str:
    """Получить роль админа. Возвращает 'full', 'content' или None."""
    conn = get_connection()
    c = conn.cursor()
    c.execute('SELECT role FROM admins WHERE user_id = ?', (user_id,))
    row = c.fetchone()
    conn.close()
    return dict(row)['role'] if row else None


def get_non_admin_users(limit: int = 30) -> list:
    """Пользователи которые ещё не являются админами."""
    conn = get_connection()
    c = conn.cursor()
    c.execute('''
        SELECT user_id, username, first_name
        FROM users
        WHERE user_id NOT IN (SELECT user_id FROM admins)
        ORDER BY registered_at DESC
        LIMIT ?
    ''', (limit,))
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows
