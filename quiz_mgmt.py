import json
import os

# Functions to add to handlers/admin.py
def load_quiz():
    from config import DATA_DIR
    path = os.path.join(DATA_DIR, 'quiz.json')
    if not os.path.exists(path):
        return {"questions": []}
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_quiz(data):
    from config import DATA_DIR
    path = os.path.join(DATA_DIR, 'quiz.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def save_settings_val(key, val):
    from config import DATA_DIR
    path = os.path.join(DATA_DIR, 'settings.json')
    data = {}
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    data[key] = val
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
